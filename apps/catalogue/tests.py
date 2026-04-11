import json
import uuid
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from catalogue.models import Product, Category, ProductVariant, ProductVariantOptionType, Tag


class CategoryModelTests(TestCase):
    """Test Category model with subcategory support."""

    def test_create_top_level_category(self):
        cat = Category.objects.create(name='Shoes')
        self.assertIsNone(cat.parent)
        self.assertFalse(cat.is_subcategory)
        self.assertEqual(str(cat), 'Shoes')

    def test_create_subcategory(self):
        parent = Category.objects.create(name='Clothing')
        sub = Category.objects.create(name='T-Shirts', parent=parent)
        self.assertTrue(sub.is_subcategory)
        self.assertEqual(sub.parent, parent)
        self.assertEqual(str(sub), 'Clothing → T-Shirts')

    def test_parent_has_subcategories(self):
        parent = Category.objects.create(name='Shoes')
        Category.objects.create(name='Sneakers', parent=parent)
        Category.objects.create(name='Boots', parent=parent)
        self.assertEqual(parent.subcategories.count(), 2)

    def test_unique_constraint(self):
        parent = Category.objects.create(name='Clothing')
        Category.objects.create(name='T-Shirts', parent=parent)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Category.objects.create(name='T-Shirts', parent=parent)

    def test_same_name_different_parent_allowed(self):
        p1 = Category.objects.create(name='Mens')
        p2 = Category.objects.create(name='Womens')
        c1 = Category.objects.create(name='Shoes', parent=p1)
        c2 = Category.objects.create(name='Shoes', parent=p2)
        self.assertNotEqual(c1.id, c2.id)


class TagModelTests(TestCase):
    """Test Tag model."""

    def test_create_tag(self):
        tag = Tag.objects.create(name='Summer')
        self.assertEqual(str(tag), 'Summer')

    def test_tag_unique(self):
        Tag.objects.create(name='Sale')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Tag.objects.create(name='Sale')

    def test_product_tags(self):
        cat = Category.objects.create(name='Clothing')
        product = Product.objects.create(name='T-Shirt', category=cat, price=500, approved=True)
        t1 = Tag.objects.create(name='New')
        t2 = Tag.objects.create(name='Featured')
        product.tags.add(t1, t2)
        self.assertEqual(product.tags.count(), 2)
        self.assertIn(product, t1.products.all())


class ProductModelTests(TestCase):
    """Test Product and Variant models."""

    def setUp(self):
        self.cat = Category.objects.create(name='Shoes')
        self.product = Product.objects.create(
            name='Nike Air Max',
            category=self.cat,
            price=Decimal('5000.00'),
            cost_price=Decimal('3000.00'),
            stock_qty=10,
            approved=True,
        )

    def test_product_creation(self):
        self.assertEqual(str(self.product), 'Nike Air Max')
        self.assertEqual(self.product.total_stock, 10)
        self.assertTrue(self.product.barcode)  # Auto-generated

    def test_variant_creation_syncs_stock(self):
        self.product.has_variants = True
        self.product.save()

        v1 = ProductVariant.objects.create(
            product=self.product,
            options={'Size': '42', 'Color': 'White'},
            price_override=Decimal('5500.00'),
            stock_qty=5,
        )
        v2 = ProductVariant.objects.create(
            product=self.product,
            options={'Size': '43', 'Color': 'Black'},
            stock_qty=3,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_qty, 8)  # 5 + 3

    def test_variant_price_fallback(self):
        v = ProductVariant.objects.create(
            product=self.product,
            options={'Size': '42'},
            stock_qty=2,
        )
        # No price_override → falls back to product price
        self.assertEqual(v.price, Decimal('5000.00'))

    def test_variant_price_override(self):
        v = ProductVariant.objects.create(
            product=self.product,
            options={'Size': '42'},
            price_override=Decimal('5500.00'),
            stock_qty=2,
        )
        self.assertEqual(v.price, Decimal('5500.00'))

    def test_variant_name(self):
        v = ProductVariant.objects.create(
            product=self.product,
            options={'Size': '42', 'Color': 'White'},
            stock_qty=1,
        )
        self.assertIn('42', str(v))
        self.assertIn('White', str(v))

    def test_option_types(self):
        ot = ProductVariantOptionType.objects.create(
            product=self.product,
            name='Size',
            values=['40', '41', '42', '43'],
        )
        self.assertEqual(str(ot), 'Nike Air Max - Size')
        self.assertEqual(len(ot.values), 4)

    def test_variants_json(self):
        self.product.has_variants = True
        self.product.save()
        ProductVariant.objects.create(
            product=self.product,
            options={'Size': '42'},
            price_override=Decimal('5500.00'),
            stock_qty=3,
        )
        data = json.loads(self.product.variants_json)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['price'], 5500.0)
        self.assertEqual(data[0]['stock_qty'], 3)
