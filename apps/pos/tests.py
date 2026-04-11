import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from catalogue.models import Product, Category, ProductVariant, ProductVariantOptionType
from pos.models import Transaction, Coupon


class POSViewTestBase(TestCase):
    """Base class with common setup for POS tests."""

    def setUp(self):
        # Create admin and cashier users
        self.admin = User.objects.create_user(
            username='admin', pin='1234', name='Admin User', role='admin'
        )
        self.cashier = User.objects.create_user(
            username='cashier', pin='5678', name='Cashier User', role='cashier'
        )

        # Create categories with subcategory
        self.cat_parent = Category.objects.create(name='Clothing')
        self.cat_sub = Category.objects.create(name='T-Shirts', parent=self.cat_parent)
        self.cat_other = Category.objects.create(name='Shoes')

        # Create products
        self.product1 = Product.objects.create(
            name='White T-Shirt', category=self.cat_sub,
            price=Decimal('1500.00'), cost_price=Decimal('800.00'),
            stock_qty=20, approved=True,
        )
        self.product2 = Product.objects.create(
            name='Running Shoes', category=self.cat_other,
            price=Decimal('5000.00'), cost_price=Decimal('3000.00'),
            stock_qty=10, approved=True,
        )
        self.product_unapproved = Product.objects.create(
            name='Draft Product', category=self.cat_parent,
            price=Decimal('999.00'), stock_qty=5, approved=False,
        )

        # Create product with variants
        self.product_variant = Product.objects.create(
            name='Polo Shirt', category=self.cat_sub,
            price=Decimal('2000.00'), has_variants=True,
            stock_qty=0, approved=True,
        )
        ProductVariantOptionType.objects.create(
            product=self.product_variant, name='Size', values=['S', 'M', 'L']
        )
        ProductVariantOptionType.objects.create(
            product=self.product_variant, name='Color', values=['White', 'Black']
        )
        self.variant_sm_w = ProductVariant.objects.create(
            product=self.product_variant,
            options={'Size': 'M', 'Color': 'White'},
            price_override=Decimal('2200.00'),
            stock_qty=5,
        )
        self.variant_sm_b = ProductVariant.objects.create(
            product=self.product_variant,
            options={'Size': 'M', 'Color': 'Black'},
            stock_qty=3,
        )

        self.client = Client()


class POSIndexTests(POSViewTestBase):
    """Test POS index view."""

    def test_index_requires_login(self):
        resp = self.client.get(reverse('pos:index'))
        self.assertEqual(resp.status_code, 302)  # Redirects to login

    def test_index_loads_for_cashier(self):
        self.client.force_login(self.cashier)
        resp = self.client.get(reverse('pos:index'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'White T-Shirt')
        self.assertContains(resp, 'Running Shoes')

    def test_index_hides_unapproved(self):
        self.client.force_login(self.cashier)
        resp = self.client.get(reverse('pos:index'))
        self.assertNotContains(resp, 'Draft Product')

    def test_index_filters_by_category(self):
        self.client.force_login(self.cashier)
        resp = self.client.get(reverse('pos:index'), {'category': self.cat_other.id})
        self.assertContains(resp, 'Running Shoes')
        self.assertNotContains(resp, 'White T-Shirt')

    def test_parent_category_includes_subcategories(self):
        """Filtering by parent category should include subcategory products."""
        self.client.force_login(self.cashier)
        resp = self.client.get(reverse('pos:index'), {'category': self.cat_parent.id})
        self.assertContains(resp, 'White T-Shirt')  # In subcategory
        self.assertContains(resp, 'Polo Shirt')      # Also in subcategory

    def test_search_filter(self):
        self.client.force_login(self.cashier)
        resp = self.client.get(reverse('pos:index'), {'q': 'running'})
        self.assertContains(resp, 'Running Shoes')
        self.assertNotContains(resp, 'White T-Shirt')

    def test_htmx_returns_partial(self):
        self.client.force_login(self.cashier)
        resp = self.client.get(reverse('pos:index'), HTTP_HX_REQUEST='true')
        self.assertEqual(resp.status_code, 200)
        # Should return partial (product_list.html), not full page
        self.assertNotContains(resp, '<!DOCTYPE html')

    def test_admin_gets_admin_context(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('pos:index'))
        self.assertEqual(resp.status_code, 200)
        # Admin context flag
        self.assertTrue(resp.context.get('is_admin', False))

    def test_cashier_not_admin_context(self):
        self.client.force_login(self.cashier)
        resp = self.client.get(reverse('pos:index'))
        self.assertFalse(resp.context.get('is_admin', True))

    def test_product_variant_data_in_context(self):
        self.client.force_login(self.cashier)
        resp = self.client.get(reverse('pos:index'))
        content = resp.content.decode()
        # Variant data should be embedded
        self.assertIn('option_types', content)


class POSCheckoutTests(POSViewTestBase):
    """Test checkout flow."""

    def test_checkout_basic(self):
        self.client.force_login(self.cashier)
        items = [{
            'id': str(self.product1.id),
            'name': 'White T-Shirt',
            'price': 1500,
            'qty': 2,
            'is_variant': False,
            'image': '📦',
            'stock_qty': 20,
        }]
        resp = self.client.post(
            reverse('pos:checkout'),
            json.dumps({'items': items, 'payment_method': 'cash'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        # Transaction created
        tx = Transaction.objects.last()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.total, Decimal('3000.00'))
        self.assertEqual(tx.payment_method, 'cash')
        # Stock decreased
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock_qty, 18)

    def test_checkout_with_price_override(self):
        """Anyone can change price at POS — original_price should be logged."""
        self.client.force_login(self.cashier)
        items = [{
            'id': str(self.product1.id),
            'name': 'White T-Shirt',
            'price': 1500,
            'sale_price': 1200,  # Price override
            'qty': 1,
            'is_variant': False,
            'image': '📦',
            'stock_qty': 20,
        }]
        resp = self.client.post(
            reverse('pos:checkout'),
            json.dumps({'items': items, 'payment_method': 'cash'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        tx = Transaction.objects.last()
        self.assertEqual(tx.total, Decimal('1200.00'))
        # Original price is logged in the items JSON
        self.assertEqual(tx.items[0]['original_price'], 1500.0)
        self.assertEqual(tx.items[0]['price'], 1200.0)

    def test_checkout_with_variant(self):
        self.client.force_login(self.cashier)
        items = [{
            'id': str(self.variant_sm_w.id),
            'name': 'Polo Shirt (M / White)',
            'price': 2200,
            'qty': 2,
            'is_variant': True,
            'parent_id': str(self.product_variant.id),
            'image': '📦',
            'stock_qty': 5,
        }]
        resp = self.client.post(
            reverse('pos:checkout'),
            json.dumps({'items': items, 'payment_method': 'mpesa'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.variant_sm_w.refresh_from_db()
        self.assertEqual(self.variant_sm_w.stock_qty, 3)

    def test_checkout_empty_cart_fails(self):
        self.client.force_login(self.cashier)
        resp = self.client.post(
            reverse('pos:checkout'),
            json.dumps({'items': [], 'payment_method': 'cash'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_checkout_with_coupon(self):
        coupon = Coupon.objects.create(
            code='SAVE10', discount_type='percent',
            discount_value=10, created_by=self.admin,
        )
        self.client.force_login(self.cashier)
        items = [{
            'id': str(self.product1.id),
            'name': 'White T-Shirt',
            'price': 1500,
            'qty': 1,
            'is_variant': False,
            'image': '📦',
            'stock_qty': 20,
        }]
        resp = self.client.post(
            reverse('pos:checkout'),
            json.dumps({'items': items, 'payment_method': 'cash', 'coupon_code': 'SAVE10'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        tx = Transaction.objects.last()
        self.assertEqual(tx.coupon_discount, Decimal('150.00'))  # 10% of 1500
        self.assertEqual(tx.total, Decimal('1350.00'))
        coupon.refresh_from_db()
        self.assertEqual(coupon.used_count, 1)


class POSReceiptTests(POSViewTestBase):
    """Test receipt views."""

    def test_receipt_print_loads(self):
        self.client.force_login(self.cashier)
        tx = Transaction.objects.create(
            cashier=self.cashier,
            items=[{'name': 'Test', 'qty': 1, 'price': 100}],
            subtotal=Decimal('100.00'),
            total=Decimal('100.00'),
            payment_method='cash',
        )
        resp = self.client.get(reverse('pos:receipt_print', args=[tx.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Back to Sales')
        self.assertContains(resp, 'ELI COLLECTION')


class POSVoidTests(POSViewTestBase):
    """Test void transaction."""

    def test_cashier_cannot_void(self):
        tx = Transaction.objects.create(
            cashier=self.cashier,
            items=[{'name': 'Test', 'qty': 1, 'price': 100}],
            subtotal=Decimal('100.00'),
            total=Decimal('100.00'),
            payment_method='cash',
        )
        self.client.force_login(self.cashier)
        resp = self.client.post(
            reverse('pos:void_transaction', args=[tx.id]),
            json.dumps({'reason': 'Wrong item'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_void(self):
        self.client.force_login(self.admin)
        tx = Transaction.objects.create(
            cashier=self.cashier,
            items=[{
                'name': 'Test', 'qty': 1, 'price': 100,
                'id': str(self.product1.id), 'is_variant': False,
            }],
            subtotal=Decimal('100.00'),
            total=Decimal('100.00'),
            payment_method='cash',
        )
        original_stock = self.product1.stock_qty
        resp = self.client.post(
            reverse('pos:void_transaction', args=[tx.id]),
            json.dumps({'reason': 'Wrong item'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['status'], 'success')
        tx.refresh_from_db()
        self.assertEqual(tx.status, 'voided')
        # Stock should be restored
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock_qty, original_stock + 1)


class CouponTests(POSViewTestBase):
    """Test coupon management."""

    def test_validate_invalid_coupon(self):
        self.client.force_login(self.cashier)
        resp = self.client.post(reverse('pos:validate_coupon'), {'code': 'FAKE', 'subtotal': '1000'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invalid')

    def test_validate_valid_coupon(self):
        Coupon.objects.create(
            code='FLAT500', discount_type='fixed',
            discount_value=500, created_by=self.admin,
        )
        self.client.force_login(self.cashier)
        resp = self.client.post(reverse('pos:validate_coupon'), {'code': 'FLAT500', 'subtotal': '2000'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Save KES')

    def test_coupon_admin_only_management(self):
        self.client.force_login(self.cashier)
        resp = self.client.get(reverse('pos:coupon_list'))
        self.assertEqual(resp.status_code, 403)

        self.client.force_login(self.admin)
        resp = self.client.get(reverse('pos:coupon_list'))
        self.assertEqual(resp.status_code, 200)


class UITests(POSViewTestBase):
    """Test UI active tab styling requirements."""

    def test_active_topbar_styles(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('pos:index'))
        content = resp.content.decode()
        self.assertIn('background:#2d545e;color:#e1b382', content)

    def test_active_bottom_nav_styles(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('pos:index'))
        content = resp.content.decode()
        self.assertIn('background: #2d545e', content)
        self.assertIn('color: #e1b382', content)
