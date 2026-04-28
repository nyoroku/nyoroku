import json
from django.test import TestCase, Client
from django.urls import reverse
from catalogue.models import Product, Category, SubCategory, FragmentSize
from accounts.models import User
from decimal import Decimal

class POSTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin', pin='1234', name='Admin User', role='admin')
        self.client = Client()
        self.client.force_login(self.user)
        
        self.cat = Category.objects.create(name='Test Cat')
        self.sub = SubCategory.objects.create(category=self.cat, name='Test Sub')
        
        # Kadogo Product
        self.soap = Product.objects.create(
            name='Soap Bar',
            subcategory=self.sub,
            base_unit_price=120.00,
            is_kadogo=True,
            whole_unit_stock=10,
            stock_qty=Decimal('0.000')
        )
        self.fragment = FragmentSize.objects.create(
            product=self.soap,
            name='Piece',
            fragment_count=7,
            fragment_price=30.00,
            fragment_pool=0
        )
        
        # Normal Product
        self.bread = Product.objects.create(
            name='Bread',
            subcategory=self.sub,
            base_unit_price=60.00,
            stock_qty=Decimal('50.000')
        )

    def test_pos_index_serialization(self):
        """Test that product_json is properly serialized to JSON in the context."""
        response = self.client.get(reverse('pos:index'))
        self.assertEqual(response.status_code, 200)
        
        products_data = response.context['products_data']
        soap_data = next(pd for pd in products_data if pd['product'].name == 'Soap Bar')
        
        p_json = json.loads(soap_data['product_json'])
        self.assertEqual(p_json['name'], 'Soap Bar')
        self.assertEqual(p_json['is_kadogo'], True)
        self.assertEqual(len(p_json['fragments']), 1)

    def test_pos_checkout_kadogo_whole(self):
        """Test checkout of a whole unit for a Kadogo product (deducts from whole_unit_stock)."""
        payload = {
            'items': [
                {
                    'product_id': str(self.soap.id),
                    'sell_mode': 'whole',
                    'quantity': 2,
                    'unit_price': 120.0,
                    'line_total': 240.0,
                }
            ],
            'payment_method': 'cash',
        }
        response = self.client.post(reverse('pos:checkout'), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.soap.refresh_from_db()
        self.assertEqual(self.soap.whole_unit_stock, 8)

    def test_pos_checkout_normal_product(self):
        """Test checkout of a normal product (deducts from stock_qty)."""
        payload = {
            'items': [
                {
                    'product_id': str(self.bread.id),
                    'sell_mode': 'whole',
                    'quantity': 5,
                    'unit_price': 60.0,
                    'line_total': 300.0,
                }
            ],
            'payment_method': 'cash',
        }
        response = self.client.post(reverse('pos:checkout'), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.bread.refresh_from_db()
        self.assertEqual(float(self.bread.stock_qty), 45.0)

    def test_pos_checkout_fragment_auto_cut(self):
        """Test that buying fragments triggers an auto-cut if the pool is empty."""
        payload = {
            'items': [
                {
                    'product_id': str(self.soap.id),
                    'sell_mode': 'fragment',
                    'quantity': 1,
                    'unit_price': 30.0,
                    'line_total': 30.0,
                    'fragment_size_id': str(self.fragment.id),
                }
            ],
            'payment_method': 'cash',
        }
        
        # Pool is 0, stock is 10.
        # Buying 1 should trigger a cut of 1 unit -> yields 7 pieces.
        # Pool becomes 7 - 1 = 6. Whole stock becomes 10 - 1 = 9.
        
        response = self.client.post(reverse('pos:checkout'), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        self.soap.refresh_from_db()
        self.fragment.refresh_from_db()
        
        self.assertEqual(self.soap.whole_unit_stock, 9)
        self.assertEqual(self.fragment.fragment_pool, 6)
