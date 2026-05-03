from django.core.management.base import BaseCommand
from catalogue.models import Category, SubCategory, Product, FragmentSize
from accounts.models import User
from decimal import Decimal

class Command(BaseCommand):
    help = 'Seeds the database with Jimmy Supermarket items (Comprehensive list)'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting Jimmy Supermarket seed...")
        
        # Ensure admin user exists for 'created_by'
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            admin = User.objects.first()
            if not admin:
                self.stdout.write(self.style.ERROR("Error: No user found. Please create one first."))
                return

        # 1. Categories
        categories_data = [
            {'name': 'Groceries', 'icon': '🥬'},
            {'name': 'Personal Care', 'icon': '🧴'},
            {'name': 'Household', 'icon': '🏠'},
            {'name': 'Meat & Poultry', 'icon': '🥩'},
            {'name': 'Bakery', 'icon': '🍞'},
            {'name': 'Fresh Produce', 'icon': '🍎'},
            {'name': 'Soft Drinks', 'icon': '🥤'},
            {'name': 'Beers & Ciders', 'icon': '🍺'},
            {'name': 'Spirits', 'icon': '🥃'},
            {'name': 'Wines', 'icon': '🍷'},
        ]

        categories = {}
        for cat_data in categories_data:
            cat, created = Category.objects.get_or_create(name=cat_data['name'], defaults={'icon': cat_data['icon']})
            categories[cat_data['name']] = cat
            if created:
                self.stdout.write(f"Created Category: {cat.name}")

        # 2. Subcategories
        subcategories_data = [
            ('Groceries', 'Staples'),
            ('Groceries', 'Dairy'),
            ('Groceries', 'Cooking Oil'),
            ('Personal Care', 'Soap & Wash'),
            ('Personal Care', 'Toothpaste'),
            ('Household', 'Cleaning'),
            ('Household', 'General'),
            ('Meat & Poultry', 'Beef'),
            ('Meat & Poultry', 'Chicken'),
            ('Bakery', 'Bread'),
            ('Fresh Produce', 'Vegetables'),
            ('Soft Drinks', 'Soda'),
            ('Soft Drinks', 'Water'),
            ('Beers & Ciders', 'Beers'),
            ('Spirits', 'Gin'),
            ('Spirits', 'Whiskey'),
            ('Wines', 'Red Wine'),
        ]

        subcats = {}
        for cat_name, sub_name in subcategories_data:
            cat = categories[cat_name]
            sub, created = SubCategory.objects.get_or_create(category=cat, name=sub_name)
            subcats[sub_name] = sub
            if created:
                self.stdout.write(f"Created SubCategory: {sub_name} under {cat_name}")

        # 3. Products - Expanded Supermarket Selection
        products_list = [
            # STAPLES & DAIRY
            {'name': 'Supa Loaf Bread 400g', 'sub': 'Bread', 'price': 65, 'cost': 50, 'sku': 'JS-001', 'img': '🍞'},
            {'name': 'KCC Milk 500ml', 'sub': 'Dairy', 'price': 60, 'cost': 45, 'sku': 'JS-002', 'img': '🥛'},
            {'name': 'Kabras Sugar 1kg', 'sub': 'Staples', 'price': 180, 'cost': 150, 'sku': 'JS-003', 'img': '🍚', 'weight': True},
            {'name': 'Ajab Wheat Flour 2kg', 'sub': 'Staples', 'price': 210, 'cost': 180, 'sku': 'JS-004', 'img': '🌾'},
            {'name': 'Pwani Fresh Fri 1L', 'sub': 'Cooking Oil', 'price': 320, 'cost': 270, 'sku': 'JS-005', 'img': '🛢️'},
            
            # PERSONAL CARE & HOUSEHOLD
            {'name': 'Geisha Soap (Pack of 4)', 'sub': 'Soap & Wash', 'price': 500, 'cost': 400, 'sku': 'JS-006', 'img': '🧼', 'split': True, 'pieces': 4, 'split_price': 135},
            {'name': 'Colgate Toothpaste 100ml', 'sub': 'Toothpaste', 'price': 150, 'cost': 120, 'sku': 'JS-007', 'img': '🪥'},
            {'name': 'JIK Bleach 500ml', 'sub': 'Cleaning', 'price': 180, 'cost': 140, 'sku': 'JS-008', 'img': '🧴'},
            {'name': 'Hanan Tissues (Pack of 4)', 'sub': 'General', 'price': 250, 'cost': 190, 'sku': 'JS-009', 'img': '🧻'},
            
            # MEAT & PRODUCE
            {'name': 'Premium Beef Steak', 'sub': 'Beef', 'price': 600, 'cost': 450, 'sku': 'JS-010', 'img': '🥩', 'weight': True},
            {'name': 'Onions 1kg', 'sub': 'Vegetables', 'price': 120, 'cost': 80, 'sku': 'JS-011', 'img': '🧅', 'weight': True},
            {'name': 'Tomatoes 1kg', 'sub': 'Vegetables', 'price': 150, 'cost': 100, 'sku': 'JS-012', 'img': '🍅', 'weight': True},

            # LIQUOR & DRINKS (Matching previous list)
            {'name': 'Tusker Lager 500ml', 'sub': 'Beers', 'price': 250, 'cost': 190, 'sku': 'JS-L001', 'img': '🍺'},
            {'name': "Gilbey's Gin 750ml", 'sub': 'Gin', 'price': 1250, 'cost': 950, 'sku': 'JS-L002', 'img': '🍸', 'kadogo': True},
            {'name': 'Jameson 750ml', 'sub': 'Whiskey', 'price': 2500, 'cost': 1900, 'sku': 'JS-L003', 'img': '🥃', 'kadogo': True},
            {'name': 'Coke 500ml', 'sub': 'Soda', 'price': 70, 'cost': 55, 'sku': 'JS-S001', 'img': '🥤'},
            {'name': 'Keringet Water 500ml', 'sub': 'Water', 'price': 50, 'cost': 35, 'sku': 'JS-S002', 'img': '💧'},
        ]

        for p_data in products_list:
            sub = subcats[p_data['sub']]
            is_kadogo = p_data.get('kadogo', False)
            is_weight = p_data.get('weight', False)
            is_split = p_data.get('split', False)

            defaults = {
                'subcategory': sub,
                'base_unit_price': Decimal(str(p_data['price'])),
                'cost_price': Decimal(str(p_data['cost'])),
                'sku': p_data['sku'],
                'image': p_data['img'],
                'created_by': admin,
                'base_unit_label': 'Unit'
            }

            if is_weight:
                defaults.update({
                    'weight_sell_enabled': True,
                    'weight_unit': 'kg',
                    'price_per_weight_unit': Decimal(str(p_data['price'])),
                    'stock_in_weight_unit': Decimal('20.0'),
                    'weight_sell_mode': 'BY_WEIGHT'
                })
            elif is_split:
                defaults.update({
                    'split_enabled': True,
                    'split_unit_label': 'Piece',
                    'split_unit_price': Decimal(str(p_data['split_price'])),
                    'pieces_per_base': p_data['pieces'],
                    'stock_qty': Decimal('10')
                })
            elif is_kadogo:
                defaults.update({
                    'is_kadogo': True,
                    'whole_unit_stock': 12,
                    'whole_unit_label': 'Bottle'
                })
            else:
                defaults['stock_qty'] = Decimal('24')

            prod, created = Product.objects.get_or_create(name=p_data['name'], defaults=defaults)
            
            if created and is_kadogo:
                FragmentSize.objects.create(
                    product=prod,
                    name='Peg (30ml)',
                    fragment_count=25,
                    fragment_price=Decimal(str(round(p_data['price'] / 20))),
                    is_default=True
                )
            
            if created:
                self.stdout.write(f"Created Product: {prod.name}")

        self.stdout.write(self.style.SUCCESS("Jimmy Supermarket Seed completed successfully."))
