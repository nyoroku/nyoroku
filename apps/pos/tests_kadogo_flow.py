import json
from django.test import TestCase, Client
from django.urls import reverse
from catalogue.models import Product, Category, SubCategory, FragmentSize
from accounts.models import User
from core.models import AuditTrail
from decimal import Decimal

class KadogoFlowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', pin='1111', name='Tester', role='admin')
        self.client = Client()
        self.client.force_login(self.user)
        
        self.cat = Category.objects.create(name='Groceries')
        self.sub = SubCategory.objects.create(category=self.cat, name='Cleaning')
        
        # Soap Bar: 10 units, 0 pieces in pool.
        # Each cut yields 10 pieces.
        self.soap = Product.objects.create(
            name='Soap Bar',
            subcategory=self.sub,
            base_unit_price=100.00,
            is_kadogo=True,
            whole_unit_stock=10,
            stock_qty=Decimal('0.000')
        )
        self.frag = FragmentSize.objects.create(
            product=self.soap,
            name='1/4 Piece',
            fragment_count=10,
            fragment_price=25.00,
            fragment_pool=0
        )

    def test_fragment_sale_triggers_auto_cut(self):
        """Buying 1 piece when pool is 0 should cut 1 whole unit and leave 9 pieces in pool."""
        payload = {
            'items': [
                {
                    'product_id': str(self.soap.id),
                    'sell_mode': 'fragment',
                    'quantity': 1,
                    'unit_price': 25.0,
                    'line_total': 25.0,
                    'fragment_size_id': str(self.frag.id),
                }
            ],
            'payment_method': 'cash',
            'cash_tendered': 30
        }
        response = self.client.post(reverse('pos:checkout'), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        self.soap.refresh_from_db()
        self.frag.refresh_from_db()
        
        # Whole stock: 10 -> 9
        self.assertEqual(self.soap.whole_unit_stock, 9)
        # Pool: 0 -> (1*10) - 1 = 9
        self.assertEqual(self.frag.fragment_pool, 9)
        
        # Verify Audit Trail
        audit = AuditTrail.objects.filter(action='sale_processed').first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.metadata['total'], '25.0')

    def test_fragment_sale_from_pool(self):
        """Buying 2 pieces when pool is 10 should leave 8 pieces and not touch whole stock."""
        self.frag.fragment_pool = 10
        self.frag.save()
        
        payload = {
            'items': [
                {
                    'product_id': str(self.soap.id),
                    'sell_mode': 'fragment',
                    'quantity': 2,
                    'unit_price': 25.0,
                    'line_total': 50.0,
                    'fragment_size_id': str(self.frag.id),
                }
            ],
            'payment_method': 'cash'
        }
        response = self.client.post(reverse('pos:checkout'), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        self.soap.refresh_from_db()
        self.frag.refresh_from_db()
        
        self.assertEqual(self.soap.whole_unit_stock, 10)
        self.assertEqual(self.frag.fragment_pool, 8)

    def test_multiple_fragment_sale_triggers_multiple_cuts(self):
        """Buying 15 pieces when each cut yields 10 should cut 2 whole units and leave 5 pieces in pool."""
        # Stock: 10 units. Pool: 0.
        # Buying 15 pieces:
        # Cut 1: Pool=10, Stock=9
        # Cut 2: Pool=20, Stock=8
        # Final Pool after sale: 20 - 15 = 5.
        
        payload = {
            'items': [
                {
                    'product_id': str(self.soap.id),
                    'sell_mode': 'fragment',
                    'quantity': 15,
                    'unit_price': 25.0,
                    'line_total': 375.0,
                    'fragment_size_id': str(self.frag.id),
                }
            ],
            'payment_method': 'cash'
        }
        response = self.client.post(reverse('pos:checkout'), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        self.soap.refresh_from_db()
        self.frag.refresh_from_db()
        
        self.assertEqual(self.soap.whole_unit_stock, 8)
        self.assertEqual(self.frag.fragment_pool, 5)
