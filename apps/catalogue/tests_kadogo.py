import uuid
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from catalogue.models import Product, Category, SubCategory, FragmentSize, CutAction, StockLedger
from procurement.models import PurchaseOrder, POLineItem, GoodsReceipt

class KadogoSellingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='admin', pin='1234', name='Admin User', role='admin'
        )
        self.client = Client()
        self.client.login(username='admin', password='1234')
        
        self.cat = Category.objects.create(name='Groceries')
        self.subcat = SubCategory.objects.create(category=self.cat, name='Soap')
        
        self.product = Product.objects.create(
            name='Ushindi Soap',
            subcategory=self.subcat,
            base_unit_label='Bar',
            base_unit_price=Decimal('100.00'),
            cost_price=Decimal('70.00'),
            is_kadogo=True,
            whole_unit_stock=10,
            created_by=self.user
        )
        
        self.frag_size = FragmentSize.objects.create(
            product=self.product,
            name='Piece',
            fragment_count=7,
            fragment_price=Decimal('15.00'),
            is_default=True
        )

    def test_manual_cut(self):
        """Test admin manually cutting a whole unit into fragments."""
        url = reverse('catalogue:manual_cut')
        data = {
            'product_id': self.product.id,
            'fragment_size_id': self.frag_size.id,
            'whole_qty': 1
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        
        self.product.refresh_from_db()
        self.frag_size.refresh_from_db()
        
        self.assertEqual(self.product.whole_unit_stock, 9)
        self.assertEqual(self.frag_size.fragment_pool, 7)
        
        # Check CutAction
        self.assertEqual(CutAction.objects.count(), 1)
        cut = CutAction.objects.first()
        self.assertEqual(cut.whole_units_cut, 1)
        self.assertEqual(cut.fragments_added, 7)
        
        # Check Ledger
        ledgers = StockLedger.objects.filter(cut_action_id=cut.id)
        self.assertEqual(ledgers.count(), 2)
        self.assertTrue(ledgers.filter(pool='WHOLE', qty_delta=-1).exists())
        self.assertTrue(ledgers.filter(pool='FRAGMENT', qty_delta=7).exists())

    def test_pos_checkout_fragment_auto_cut(self):
        """Test POS checkout triggers an auto-cut when fragments are empty."""
        # Set stock to exactly 1 bar and 0 pieces
        self.product.whole_unit_stock = 1
        self.product.save()
        self.frag_size.fragment_pool = 0
        self.frag_size.save()
        
        url = reverse('pos:checkout')
        cart_data = {
            'items': [{
                'product_id': str(self.product.id),
                'sell_mode': 'fragment',
                'fragment_size_id': str(self.frag_size.id),
                'quantity': 1,
                'unit_price': 15.00
            }],
            'payment_method': 'cash',
            'cash_tendered': 20.00
        }
        
        response = self.client.post(
            url, 
            data=cart_data, 
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        self.product.refresh_from_db()
        self.frag_size.refresh_from_db()
        
        # Auto-cut should have happened: 1 bar -> 0 bars, 0 pieces -> (7-1) = 6 pieces
        self.assertEqual(self.product.whole_unit_stock, 0)
        self.assertEqual(self.frag_size.fragment_pool, 6)
        
        self.assertEqual(CutAction.objects.count(), 1)
        self.assertEqual(CutAction.objects.first().triggered_by, 'SALE')

    def test_procurement_receipt_populates_whole_pool(self):
        """Test that receiving goods for a Kadogo product populates whole_unit_stock."""
        from procurement.models import Supplier
        supplier = Supplier.objects.create(name='Global Soap Co')
        
        po = PurchaseOrder.objects.create(
            supplier=supplier,
            created_by=self.user,
            status='approved'
        )
        POLineItem.objects.create(
            po=po,
            product=self.product,
            ordered_qty=5,
            unit_cost=70.00
        )
        
        # Receive goods
        url = reverse('procurement:po_receive', args=[po.pk])
        # Find the line item ID
        line = po.line_items.first()
        data = {
            'received_qty_' + str(line.id): 5,
            'notes': 'Fresh delivery'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        
        self.product.refresh_from_db()
        # Should have added 5 bars to the whole unit pool (initial 10 + 5 = 15)
        self.assertEqual(self.product.whole_unit_stock, 15)
        # Verify ledger
        ledger = StockLedger.objects.filter(entry_type='GRN', product=self.product).first()
        self.assertEqual(ledger.pool, 'WHOLE')
        self.assertEqual(ledger.qty_delta, 5)
