from django.test import TestCase, Client
from django.urls import reverse
from decimal import Decimal
from catalogue.models import Product, Category, SubCategory
from accounts.models import User

class InventoryTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='admin',
            pin='1234',
            role='admin',
            name='Admin User'
        )
        self.client.login(username='admin', password='1234')
        
        self.category = Category.objects.create(name='General', order=1)
        self.subcategory = SubCategory.objects.create(category=self.category, name='Misc', order=1)

    def test_add_product_split_sell(self):
        url = reverse('catalogue:add_product')
        data = {
            'name': 'Split Test Product',
            'subcategory_id': str(self.subcategory.id),
            'base_unit_label': 'Pack',
            'base_unit_price': '100.00',
            'cost_price': '50.00',
            'split_enabled': 'on',
            'split_unit_label': 'Stick',
            'split_unit_price': '10.00',
            'pieces_per_base': '10',
            'split_min_qty': '1'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302) # Redirects to inventory
        
        product = Product.objects.get(name='Split Test Product')
        self.assertTrue(product.split_enabled)
        self.assertEqual(product.split_unit_label, 'Stick')
        self.assertEqual(product.split_unit_price, Decimal('10.00'))
        self.assertEqual(product.pieces_per_base, 10)

    def test_edit_product_kadogo(self):
        product = Product.objects.create(
            name='Kadogo Product',
            subcategory=self.subcategory,
            base_unit_price=Decimal('500.00'),
            is_kadogo=True,
            whole_unit_label='Bar',
            created_by=self.user
        )
        
        url = reverse('catalogue:edit_product')
        data = {
            'id': str(product.id),
            'name': 'Updated Kadogo',
            'is_kadogo': 'on',
            'whole_unit_label': 'Chunk',
            'new_frag_name': 'Quarter',
            'new_frag_count': '4',
            'new_frag_price': '150.00'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        
        product.refresh_from_db()
        self.assertEqual(product.name, 'Updated Kadogo')
        self.assertEqual(product.whole_unit_label, 'Chunk')
        self.assertEqual(product.fragment_sizes.count(), 1)
        self.assertEqual(product.fragment_sizes.first().name, 'Quarter')

    def test_add_product_missing_name(self):
        url = reverse('catalogue:add_product')
        data = {
            'name': '',
            'subcategory_id': str(self.subcategory.id)
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Product name is required', response.content)
