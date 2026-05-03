from django.core.management.base import BaseCommand
from catalogue.models import Category, SubCategory, Product, FragmentSize
from accounts.models import User
from decimal import Decimal

class Command(BaseCommand):
    help = 'Seeds the database with Jimmy Mini Mart items (Comprehensive Retail List)'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting Jimmy Mini Mart seed...")
        
        # Ensure admin user exists for 'created_by'
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            admin = User.objects.first()
            if not admin:
                self.stdout.write(self.style.ERROR("Error: No user found. Please create one first."))
                return

        # 1. Categories
        categories_data = [
            {'name': 'Food Staples', 'icon': '🍚'},
            {'name': 'Beverages', 'icon': '🥤'},
            {'name': 'Snacks & Biscuits', 'icon': '🍪'},
            {'name': 'Dairy & Bakery', 'icon': '🍞'},
            {'name': 'Personal Care', 'icon': '🧴'},
            {'name': 'Household', 'icon': '🏠'},
            {'name': 'Stationery', 'icon': '✏️'},
            {'name': 'Medicines', 'icon': '💊'},
            {'name': 'Airtime', 'icon': '📱'},
            {'name': 'Bags & Packaging', 'icon': '🛍️'},
        ]

        categories = {}
        for cat_data in categories_data:
            cat, created = Category.objects.get_or_create(name=cat_data['name'], defaults={'icon': cat_data['icon']})
            categories[cat_data['name']] = cat

        # 2. Subcategories
        subcategories_data = [
            ('Food Staples', 'Flour & Grain'),
            ('Food Staples', 'Cooking Oil & Fat'),
            ('Food Staples', 'Sugar & Salt'),
            ('Food Staples', 'Seasoning'),
            ('Beverages', 'Tea & Coffee'),
            ('Beverages', 'Soda & Juice'),
            ('Beverages', 'Water'),
            ('Snacks & Biscuits', 'Biscuits'),
            ('Snacks & Biscuits', 'Candy'),
            ('Dairy & Bakery', 'Milk'),
            ('Dairy & Bakery', 'Bread & Bakery'),
            ('Personal Care', 'Soap & Wash'),
            ('Personal Care', 'Baby Care'),
            ('Personal Care', 'Hair & Beauty'),
            ('Household', 'Lighting & Power'),
            ('Household', 'Cleaning Supplies'),
            ('Household', 'General Household'),
            ('Stationery', 'Books'),
            ('Stationery', 'Writing & Other'),
        ]

        subcats = {}
        for cat_name, sub_name in subcategories_data:
            cat = categories[cat_name]
            sub, created = SubCategory.objects.get_or_create(category=cat, name=sub_name)
            subcats[sub_name] = sub

        # 3. Products Data
        products_list = [
            ('Airtime Airtel 10', 'Writing & Other', 10, '📱', 'JM-A001'),
            ('Airtime Airtel 20', 'Writing & Other', 20, '📱', 'JM-A002'),
            ('Airtime Safaricom 50', 'Writing & Other', 50, '📱', 'JM-A003'),
            ('Airtime Safaricom 100', 'Writing & Other', 100, '📱', 'JM-A004'),
            ('Supa Loaf Bread 400g', 'Bread & Bakery', 70, '🍞', 'JM-B001'),
            ('Ajab Wheat Flour 2kg', 'Flour & Grain', 195, '🌾', 'JM-F001'),
            ('Kabras Sugar 1kg', 'Sugar & Salt', 160, '🍚', 'JM-S001'),
            ('KCC Fresh Milk 500ml', 'Milk', 60, '🥛', 'JM-M001'),
            ('Blueband 250g', 'Bread & Bakery', 180, '🧈', 'JM-D001'),
            ('Salit Cooking Oil 1L', 'Cooking Oil & Fat', 300, '🛢️', 'JM-O001'),
            ('Happy Happy Biscuits', 'Biscuits', 5, '🍪', 'JM-BS001'),
            ('Nuvita Milk Biscuits', 'Biscuits', 5, '🍪', 'JM-BS002'),
            ('Tropical Mints', 'Candy', 5, '🍬', 'JM-C001', 3, 10),
            ('PK Pack', 'Candy', 25, '🍬', 'JM-C004'),
            ('Nescafe 3-in-1', 'Tea & Coffee', 25, '☕', 'JM-BV001'),
            ('Eden Tea 50g', 'Tea & Coffee', 20, '🍵', 'JM-BV002'),
            ('Coca Cola 500ml PET', 'Soda & Juice', 80, '🥤', 'JM-BV003'),
            ('Dasani Water 500ml', 'Water', 45, '💧', 'JM-BV004'),
            ('Geisha Soap 200g', 'Soap & Wash', 130, '🧼', 'JM-PC001'),
            ('Arimis Jelly 200ml', 'Baby Care', 130, '🧴', 'JM-PC002'),
            ('Always Pads', 'Baby Care', 80, '🩸', 'JM-PC003'),
            ('Eveready AA Battery', 'Lighting & Power', 80, '🔋', 'JM-H001'),
            ('Matchbox', 'General Household', 5, '🔥', 'JM-H003'),
            ('Toilex Tissue', 'Cleaning Supplies', 40, '🧻', 'JM-H005'),
            ('Ex. Book A5 80pg', 'Books', 40, '📓', 'JM-ST001'),
            ('Biro Pen BIC', 'Writing & Other', 25, '🖊️', 'JM-ST002'),
            ('Panadol Extra', 'Writing & Other', 20, '💊', 'JM-MD001'),
        ]

        for p_data in products_list:
            name = p_data[0]
            sub_name = p_data[1]
            price = Decimal(str(p_data[2]))
            icon = p_data[3]
            sku = p_data[4]
            bundle_qty = p_data[5] if len(p_data) > 5 else 1
            bundle_price = Decimal(str(p_data[6])) if len(p_data) > 6 else Decimal('0.00')

            sub = subcats.get(sub_name)
            
            # Using name for lookup to avoid UniqueConstraint errors with existing data
            Product.objects.update_or_create(
                name=name,
                defaults={
                    'subcategory': sub,
                    'base_unit_price': price,
                    'cost_price': price * Decimal('0.8'),
                    'sku': sku,
                    'image': icon,
                    'created_by': admin,
                    'stock_qty': Decimal('50'),
                    'bundle_pricing_enabled': (bundle_qty > 1),
                    'bundle_qty': bundle_qty,
                    'bundle_price': bundle_price,
                    'allow_single_sale': True,
                    'single_unit_price': price
                }
            )
            self.stdout.write(f"Processed Product: {name}")

        self.stdout.write(self.style.SUCCESS("Jimmy Mini Mart Seed completed successfully."))
