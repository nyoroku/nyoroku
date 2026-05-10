from decimal import Decimal
import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
User = get_user_model()
from catalogue.models import Product, SubCategory, Category

class CookingOilSellingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='cashier1',
            password='password123',
            role='cashier',
            pin='1234',
            name='Test Cashier'
        )
        self.client.force_login(self.user)
        
        self.category = Category.objects.create(name='Groceries')
        self.subcategory = SubCategory.objects.create(category=self.category, name='Oils')
        
        # Create Cooking Oil
        # Unit: Litres (L)
        # Price: 400 KES per Litre
        # Stock: 2.915 Litres
        self.oil = Product.objects.create(
            name='Cooking Oil (Dispenser)',
            subcategory=self.subcategory,
            weight_sell_enabled=True,
            weight_unit='L',
            price_per_weight_unit=Decimal('400.00'),
            stock_in_weight_unit=Decimal('2.915'),
            base_unit_price=Decimal('0.00'),  # unused for weight
            is_active=True,
            created_by=self.user
        )

    def test_scenario_1_cashier_enters_cash_amount(self):
        """
        Scenario: The customer says "Give me 100 bob of cooking oil".
        The cashier selects "By Cash" and types "100".
        The frontend calculates: 100 KES / 400 KES/L = 0.25 Litres.
        The frontend sends weight_value: 0.25 to the backend.
        """
        # Frontend calculates weight based on cash
        cash_input = 100
        price_per_l = 400
        weight_value = cash_input / price_per_l  # 0.25
        
        payload = {
            'payment_method': 'cash',
            'cash_tendered': 100,
            'items': [
                {
                    'product_id': str(self.oil.id),
                    'sell_mode': 'weight',
                    'quantity': 1,
                    'unit_price': 400,
                    'line_total': 100,
                    'weight_value': weight_value,  # 0.25
                    'weight_unit': 'L'
                }
            ]
        }
        
        response = self.client.post(
            reverse('pos:checkout'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        self.oil.refresh_from_db()
        # Initial stock: 2.915
        # Deducted: 0.250
        # Expected remaining: 2.665 L
        self.assertEqual(self.oil.stock_in_weight_unit, Decimal('2.665'))
        print("\n[TEST 1 PASSED] When cashier entered '100' as CASH, the system deducted exactly 0.25 L (250ml) and balance is 2.665 L.")

    def test_scenario_2_cashier_enters_exact_weight(self):
        """
        Scenario: The customer asks for 100ml.
        The cashier selects "By Weight" and correctly types "0.1" (Since the unit is L).
        The frontend sends weight_value: 0.1 to the backend.
        """
        payload = {
            'payment_method': 'cash',
            'cash_tendered': 40,
            'items': [
                {
                    'product_id': str(self.oil.id),
                    'sell_mode': 'weight',
                    'quantity': 1,
                    'unit_price': 400,
                    'line_total': 40,  # 0.1 * 400 = 40 KES
                    'weight_value': 0.1,  # 100 ml = 0.1 L
                    'weight_unit': 'L'
                }
            ]
        }
        
        response = self.client.post(
            reverse('pos:checkout'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        self.oil.refresh_from_db()
        # Initial stock: 2.915
        # Deducted: 0.100
        # Expected remaining: 2.815 L
        self.assertEqual(self.oil.stock_in_weight_unit, Decimal('2.815'))
        print("\n[TEST 2 PASSED] When cashier correctly entered '0.1' as WEIGHT (100ml), the system deducted exactly 0.1 L and balance is 2.815 L.")

    def test_scenario_3_cashier_accidentally_enters_100_in_weight(self):
        """
        Scenario: The cashier wants to sell 100ml, but mistakenly types '100' in the Weight field.
        Since the unit is Litres, typing 100 means 100 Litres!
        The backend should reject this because there is insufficient stock (only 2.915 L available).
        """
        payload = {
            'payment_method': 'cash',
            'cash_tendered': 40000,
            'items': [
                {
                    'product_id': str(self.oil.id),
                    'sell_mode': 'weight',
                    'quantity': 1,
                    'unit_price': 400,
                    'line_total': 40000,  # 100 L * 400 = 40,000 KES
                    'weight_value': 100,  # Cashier accidentally typed 100 here!
                    'weight_unit': 'L'
                }
            ]
        }
        
        response = self.client.post(
            reverse('pos:checkout'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Should fail with 400 Bad Request because stock < 100
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Insufficient stock', response.content)
        
        self.oil.refresh_from_db()
        # Stock should remain untouched
        self.assertEqual(self.oil.stock_in_weight_unit, Decimal('2.915'))
        print("\n[TEST 3 PASSED] When cashier mistakenly typed '100' in the WEIGHT field, the system rejected it as Insufficient Stock (tried to deduct 100 Litres).")
