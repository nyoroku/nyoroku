import json
from django.test import TestCase, Client
from django.urls import reverse
from catalogue.models import Category, Product, ProductVariant
from django.contrib.auth import get_user_model

User = get_user_model()

class POSTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', pin='1234', name='Test Admin', role='admin')
        self.client.login(username='testuser', password='1234')
        
        self.category = Category.objects.create(name="Electronics")
        self.product = Product.objects.create(
            name="Laptop",
            category=self.category,
            price=1500.00,
            stock_qty=10,
            approved=True
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            options={"Color": "Black"},
            price_override=1600.00,
            stock_qty=5
        )
        self.product.has_variants = True
        self.product.save()

    def test_pos_index_context_data(self):
        """Verify that the POS index view populates the context with safe_variants_json and other required attributes."""
        url = reverse('pos:index')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Check that products in context have the expected extra attributes
        products = response.context['products']
        found_product = None
        for p in products:
            if p.id == self.product.id:
                found_product = p
                break
        
        self.assertIsNotNone(found_product)
        self.assertTrue(hasattr(found_product, 'safe_variants_json'))
        self.assertTrue(hasattr(found_product, 'safe_price'))
        
        # Verify JSON validity
        variants_data = json.loads(found_product.safe_variants_json)
        self.assertEqual(len(variants_data), 1)
        self.assertEqual(variants_data[0]['name'], self.variant.name if hasattr(self.variant, 'name') else str(self.variant.options))

    def test_safe_price_handling(self):
        """Verify that safe_price handles null prices correctly."""
        p_no_price = Product.objects.create(
            name="Free Item",
            category=self.category,
            price=0,
            stock_qty=1
        )
        url = reverse('pos:index')
        response = self.client.get(url)
        products = response.context['products']
        
        target = next(p for p in products if p.id == p_no_price.id)
        self.assertEqual(target.safe_price, 0.0)
