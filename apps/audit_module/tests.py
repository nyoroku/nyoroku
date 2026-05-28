from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from catalogue.models import Product, Category, SubCategory
from audit_module.models import AuditSession, AuditItem

class StockAuditTestCase(TestCase):
    def setUp(self):
        # Create admin user
        self.admin = User.objects.create_user(
            username='admin_test',
            pin='1234',
            role='admin',
            name='Test Admin'
        )
        self.client = Client()
        self.client.force_login(self.admin)

        # Create catalogue objects
        self.category = Category.objects.create(name='Groceries')
        self.subcategory = SubCategory.objects.create(name='Beverages', category=self.category)
        
        # Product 1: standard item
        self.product1 = Product.objects.create(
            name='Soda Can',
            sku='SODA01',
            subcategory=self.subcategory,
            base_unit_price=Decimal('50.00'),
            stock_qty=Decimal('20.000'),
            weight_sell_enabled=False
        )
        
        # Product 2: weight based item
        self.product2 = Product.objects.create(
            name='Sugar bulk',
            sku='SUGAR01',
            subcategory=self.subcategory,
            base_unit_price=Decimal('120.00'),
            price_per_weight_unit=Decimal('120.00'),
            stock_in_weight_unit=Decimal('10.500'),
            weight_sell_enabled=True
        )

        # Initiate an audit session containing both items
        self.session = AuditSession.objects.create(
            initiated_by=self.admin,
            scope='all',
            sample_size=2
        )
        
        self.item1 = AuditItem.objects.create(
            session=self.session,
            product=self.product1,
            system_qty=self.product1.stock_qty
        )
        
        self.item2 = AuditItem.objects.create(
            session=self.session,
            product=self.product2,
            system_qty=self.product2.stock_in_weight_unit
        )

    def test_submit_audit_success(self):
        """Test submitting physical counts for items in the audit session."""
        submit_url = reverse('audit_module:submit', kwargs={'pk': self.session.pk})
        
        # Simulate form submit where only item1 is entered, item2 is left empty (omitted from POST)
        post_data = {
            f'physical_{self.item1.pk}': '18.000',
            f'note_{self.item1.pk}': 'Damaged cans',
            'session_notes': 'Completed standard items audit'
        }
        
        response = self.client.post(submit_url, post_data)
        
        # Check redirection back to detail page
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('audit_module:detail', kwargs={'pk': self.session.pk}))
        
        # Refresh from database
        self.session.refresh_from_db()
        self.item1.refresh_from_db()
        self.item2.refresh_from_db()
        self.product1.refresh_from_db()
        self.product2.refresh_from_db()
        
        # Verify session status is completed
        self.assertEqual(self.session.status, 'completed')
        self.assertEqual(self.session.notes, 'Completed standard items audit')
        
        # Verify audited item 1 fields, but stock is NOT changed automatically
        self.assertEqual(self.item1.physical_qty, Decimal('18.000'))
        self.assertEqual(self.item1.variance, Decimal('-2.000'))
        self.assertEqual(self.item1.note, 'Damaged cans')
        self.assertEqual(self.product1.stock_qty, Decimal('20.000')) # NOT adjusted automatically
        self.assertEqual(self.item1.action_status, 'pending')
        
        # Now test single item apply
        apply_url = reverse('audit_module:item_apply', kwargs={'item_id': self.item1.pk})
        apply_response = self.client.post(apply_url)
        self.assertEqual(apply_response.status_code, 302)
        
        self.product1.refresh_from_db()
        self.item1.refresh_from_db()
        self.assertEqual(self.product1.stock_qty, Decimal('18.000')) # Now adjusted!
        self.assertEqual(self.item1.action_status, 'applied')
        
        # Verify StockLedger entry was created
        from catalogue.models import StockLedger
        ledger_entry = StockLedger.objects.filter(product=self.product1, entry_type='ADJUSTMENT').first()
        self.assertIsNotNone(ledger_entry)
        self.assertEqual(ledger_entry.qty_delta, -2)
        
        # Verify untouched item 2 was skipped and remains unchanged
        self.assertIsNone(self.item2.physical_qty)
        self.assertIsNone(self.item2.variance)
        self.assertEqual(self.product2.stock_in_weight_unit, Decimal('10.500'))

    def test_initiate_audit_all_success(self):
        """Test initiating an audit for all products."""
        initiate_url = reverse('audit_module:initiate')
        post_data = {
            'scope': 'all'
        }
        response = self.client.post(initiate_url, post_data)
        
        # Check redirection to the newly created audit detail page
        self.assertEqual(response.status_code, 302)
        
        # Verify the session is created and populated with products
        session = AuditSession.objects.exclude(pk=self.session.pk).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.scope, 'all')
        self.assertEqual(session.sample_size, 2) # both self.product1 and self.product2
        self.assertEqual(session.items.count(), 2)

    def test_initiate_audit_category_success(self):
        """Test initiating a category-scoped audit with sample size."""
        initiate_url = reverse('audit_module:initiate')
        post_data = {
            'scope': 'category',
            'category_id': str(self.category.pk),
            'sample_size': 1
        }
        response = self.client.post(initiate_url, post_data)
        
        # Check redirect
        self.assertEqual(response.status_code, 302)
        
        # Verify the session is created and populated with exactly 1 product
        session = AuditSession.objects.exclude(pk=self.session.pk).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.scope, 'category')
        self.assertEqual(session.scope_category, self.category)
        self.assertEqual(session.sample_size, 1)
        self.assertEqual(session.items.count(), 1)
