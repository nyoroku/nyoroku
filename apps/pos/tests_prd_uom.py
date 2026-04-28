from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from catalogue.models import Category, SubCategory, Product, StockLedger
from procurement.models import Supplier, PurchaseOrder, POLineItem
from pos.models import Sale, SaleLineItem

User = get_user_model()

class PRDUoMAndBundleTest(TestCase):
    def setUp(self):
        # 1. User
        self.user = User.objects.create_user(
            username='testadmin',
            pin='1234',
            name='Test Admin',
            role='admin'
        )
        self.client = Client()
        login_success = self.client.login(username='testadmin', password='1234')
        if not login_success:
            print("DEBUG: Login failed! Check UserManager or User password hashing.")
        self.assertTrue(login_success, "Login failed in test setUp")

        # 2. Catalogue
        self.category = Category.objects.create(name='Snacks')
        self.subcategory = SubCategory.objects.create(category=self.category, name='Sweets')

        self.product = Product.objects.create(
            name='Tropimints',
            subcategory=self.subcategory,
            base_unit_label='Piece',
            base_unit_price=Decimal('20.00'),
            cost_price=Decimal('10.00'),
            
            # UoM
            purchase_unit_label='Packet',
            units_per_purchase=50, # 1 Packet = 50 Pieces
            
            # Bundle Pricing
            bundle_pricing_enabled=True,
            bundle_qty=3,
            bundle_price=Decimal('50.00'),
            allow_single_sale=True,
            single_unit_price=Decimal('20.00'),
            
            stock_qty=Decimal('0')
        )

        # 3. Procurement Supplier
        self.supplier = Supplier.objects.create(name='Kenafric')

    def test_01_grn_uom_conversion(self):
        """FR-03, FR-04: Receiving goods in purchase units converts to base units."""
        po = PurchaseOrder.objects.create(supplier=self.supplier, created_by=self.user)
        po_item = POLineItem.objects.create(
            po=po, product=self.product,
            ordered_qty=2, received_qty=0, unit_cost=Decimal('500.00')
        )
        po.status = 'approved'
        po.save()

        # Receive 2 packets
        response = self.client.post(f'/procurement/{po.id}/receive/', {
            f'received_qty_{po_item.id}': '2'
        }, HTTP_HX_REQUEST='true')
        
        if response.status_code != 302:
            print(f"DEBUG: test_01 response status: {response.status_code}")
            print(f"DEBUG: test_01 response content: {response.content}")
        
        self.assertEqual(response.status_code, 302)

        self.product.refresh_from_db()
        # 2 packets * 50 pieces/packet = 100 pieces
        self.assertEqual(self.product.stock_qty, Decimal('100.00'))

        # Check StockLedger
        ledger = StockLedger.objects.filter(product=self.product, entry_type='GRN').first()
        self.assertIsNotNone(ledger)
        self.assertEqual(ledger.qty_delta, 100)
        self.assertEqual(ledger.purchase_unit_qty, 2)
        self.assertEqual(ledger.purchase_unit_label_snapshot, 'Packet')

    def test_02_pos_checkout_bundle_and_single(self):
        """FR-05, FR-06, FR-09: POS checkout handles bundles correctly and logs to ledger."""
        self.product.stock_qty = Decimal('100.00')
        self.product.save()

        # Construct cart payload
        payload = {
            'items': [
                {
                    'product_id': str(self.product.id),
                    'quantity': '2', # 2 Bundles
                    'unit_price': '50.00',
                    'sell_mode': 'bundle'
                },
                {
                    'product_id': str(self.product.id),
                    'quantity': '4', # 4 Singles
                    'unit_price': '20.00',
                    'sell_mode': 'single'
                }
            ],
            'payment_method': 'cash',
            'amount_paid': '180.00'
        }
        
        # Verify Sale & Line Items
        import json
        response = self.client.post(
            '/pos/checkout/', 
            data=json.dumps(payload),
            content_type='application/json'
        )
        if response.status_code != 200:
            print(f"DEBUG: test_02 response status: {response.status_code}")
            print(f"DEBUG: test_02 response content: {response.content}")
        self.assertEqual(response.status_code, 200)

        # Verify Stock Deduction
        self.product.refresh_from_db()
        # 2 bundles * 3 pieces = 6 pieces
        # 4 singles = 4 pieces
        # Total deduction = 10 pieces. Stock = 100 - 10 = 90.
        self.assertEqual(self.product.stock_qty, Decimal('90.00'))

        # Verify Sale & Line Items
        sale = Sale.objects.first()
        self.assertIsNotNone(sale)
        
        bundle_item = sale.line_items.get(sell_mode='bundle')
        self.assertEqual(bundle_item.bundle_size_snapshot, 3)
        self.assertEqual(bundle_item.bundle_price_snapshot, Decimal('50.00'))
        
        single_item = sale.line_items.get(sell_mode='single')
        self.assertTrue(single_item.is_singles_sale)

        # Verify StockLedger Entries
        ledgers = StockLedger.objects.filter(product=self.product, entry_type='SALE')
        self.assertEqual(ledgers.count(), 2)
        
        bundle_ledger = ledgers.get(bundle_size_snapshot__isnull=False)
        self.assertEqual(bundle_ledger.qty_delta, -6)
        self.assertEqual(bundle_ledger.bundle_qty_sold, 2)
        
        single_ledger = ledgers.get(is_singles_sale=True)
        self.assertEqual(single_ledger.qty_delta, -4)

    def test_03_pos_insufficient_stock(self):
        """FR-07: Hard block if stock is insufficient for base units requested."""
        self.product.stock_qty = Decimal('5.00') # 5 pieces available
        self.product.save()

        # Try selling 2 bundles (6 pieces)
        payload = {
            'items': [
                {
                    'product_id': str(self.product.id),
                    'quantity': '2',
                    'unit_price': '50.00',
                    'sell_mode': 'bundle'
                }
            ],
            'payment_method': 'cash',
            'amount_paid': '100.00'
        }
        
        # Try selling 2 bundles (6 pieces)
        import json
        response = self.client.post(
            '/pos/checkout/', 
            data=json.dumps(payload),
            content_type='application/json'
        )
        # Should fail with 400
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Insufficient stock', response.content)

    def test_04_buy_packet_sell_units(self):
        """Verify the full flow: buy 1 packet (x50), check unit cost, sell 50 individual units."""
        # Buy 1 Packet for KES 500
        po = PurchaseOrder.objects.create(supplier=self.supplier, created_by=self.user)
        po_item = POLineItem.objects.create(
            po=po, product=self.product,
            ordered_qty=1, received_qty=0, unit_cost=Decimal('500.00')
        )
        po.status = 'approved'
        po.save()

        self.client.post(f'/procurement/{po.id}/receive/', {
            f'received_qty_{po_item.id}': '1'
        }, HTTP_HX_REQUEST='true')

        self.product.refresh_from_db()
        # Stock should be 50 units
        self.assertEqual(self.product.stock_qty, Decimal('50.00'))
        # Unit Cost should be 500 / 50 = 10.00
        self.assertEqual(self.product.cost_price, Decimal('10.00'))

        # Sell 50 units individually
        payload = {
            'items': [
                {
                    'product_id': str(self.product.id),
                    'quantity': '50',
                    'unit_price': '20.00',
                    'sell_mode': 'single'
                }
            ],
            'payment_method': 'cash',
            'amount_paid': '1000.00'
        }
        import json
        self.client.post('/pos/checkout/', data=json.dumps(payload), content_type='application/json')

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_qty, Decimal('0.00'))

