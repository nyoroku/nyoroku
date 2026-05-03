from django.core.management.base import BaseCommand
from catalogue.models import Category, SubCategory, Product, FragmentSize
from accounts.models import User
from decimal import Decimal

class Command(BaseCommand):
    help = 'Seeds the database with Jimmy Mini Mart items (Liquor & Groceries)'

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
            {'name': 'Groceries', 'icon': '🥬'},
            {'name': 'Personal Care', 'icon': '🧴'},
            {'name': 'Meat & Poultry', 'icon': '🥩'},
            {'name': 'Bakery', 'icon': '🍞'},
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
            ('Personal Care', 'Soap & Wash'),
            ('Meat & Poultry', 'Beef'),
            ('Meat & Poultry', 'Chicken'),
            ('Bakery', 'Bread'),
            ('Soft Drinks', 'Soda'),
            ('Soft Drinks', 'Sweets'),
            ('Beers & Ciders', 'Beers'),
            ('Beers & Ciders', 'Ciders'),
            ('Spirits', 'Gin'),
            ('Spirits', 'Vodka'),
            ('Spirits', 'Whiskey'),
            ('Spirits', 'Brandy'),
            ('Wines', 'Red Wine'),
            ('Wines', 'White Wine'),
            ('Soft Drinks', 'Soda'),
            ('Soft Drinks', 'Water'),
            ('Soft Drinks', 'Energy Drinks'),
        ]

        subcats = {}
        for cat_name, sub_name in subcategories_data:
            cat = categories[cat_name]
            sub, created = SubCategory.objects.get_or_create(category=cat, name=sub_name)
            subcats[sub_name] = sub
            if created:
                self.stdout.write(f"Created SubCategory: {sub_name} under {cat_name}")

        # 3. Products - Groceries (from seed.py)
        groceries_list = [
            {'name': 'Supa Loaf Bread 400g', 'sub': 'Bread', 'price': 65, 'cost': 50, 'sku': 'JM-G001', 'img': '🍞'},
            {'name': 'KCC Milk 500ml', 'sub': 'Dairy', 'price': 60, 'cost': 45, 'sku': 'JM-G002', 'img': '🥛'},
            {'name': 'Kabras Sugar 1kg', 'sub': 'Staples', 'price': 180, 'cost': 150, 'sku': 'JM-G003', 'img': '🍚', 'weight': True},
            {'name': 'Premium Beef Steak', 'sub': 'Beef', 'price': 600, 'cost': 450, 'sku': 'JM-G004', 'img': '🥩', 'weight': True},
            {'name': 'Geisha Soap (Pack of 4)', 'sub': 'Soap & Wash', 'price': 500, 'cost': 400, 'sku': 'JM-G005', 'img': '🧼', 'split': True, 'pieces': 4, 'split_price': 135},
        ]

        for p_data in groceries_list:
            sub = subcats[p_data['sub']]
            defaults = {
                'subcategory': sub,
                'base_unit_price': Decimal(str(p_data['price'])),
                'cost_price': Decimal(str(p_data['cost'])),
                'sku': p_data['sku'],
                'image': p_data['img'],
                'created_by': admin,
                'base_unit_label': 'Unit'
            }
            if p_data.get('weight'):
                defaults.update({
                    'weight_sell_enabled': True,
                    'weight_unit': 'kg',
                    'price_per_weight_unit': Decimal(str(p_data['price'])),
                    'stock_in_weight_unit': Decimal('50.0'),
                    'weight_sell_mode': 'BY_WEIGHT'
                })
            elif p_data.get('split'):
                defaults.update({
                    'split_enabled': True,
                    'split_unit_label': 'Piece',
                    'split_unit_price': Decimal(str(p_data['split_price'])),
                    'pieces_per_base': p_data['pieces'],
                    'stock_qty': Decimal('10')
                })
            else:
                defaults['stock_qty'] = Decimal('20')

            prod, created = Product.objects.get_or_create(name=p_data['name'], defaults=defaults)
            if created:
                self.stdout.write(f"Created Grocery: {prod.name}")

        # 4. Products - Liquor (from Image)
        liquor_list = [
            # BEERS
            {'name': 'Tusker Lager 500ml', 'sub': 'Beers', 'price': 250, 'cost': 190, 'sku': 'JM-L001', 'img': '🍺'},
            {'name': 'Guinness 500ml', 'sub': 'Beers', 'price': 280, 'cost': 210, 'sku': 'JM-L002', 'img': '🍺'},
            {'name': 'Savannah Cider 500ml', 'sub': 'Ciders', 'price': 300, 'cost': 230, 'sku': 'JM-L003', 'img': '🍏'},
            
            # SPIRITS
            {'name': "Gilbey's Gin 750ml", 'sub': 'Gin', 'price': 1250, 'cost': 950, 'sku': 'JM-L004', 'img': '🍸', 'kadogo': True},
            {'name': 'Chrome Vodka 250ml', 'sub': 'Vodka', 'price': 300, 'cost': 240, 'sku': 'JM-L005', 'img': '🍸'},
            {'name': 'Jameson 750ml', 'sub': 'Whiskey', 'price': 2500, 'cost': 1900, 'sku': 'JM-L006', 'img': '🥃', 'kadogo': True},
            
            # WINES
            {'name': '4th Street Red 750ml', 'sub': 'Red Wine', 'price': 1200, 'cost': 900, 'sku': 'JM-L007', 'img': '🍷'},

            # SOFT DRINKS
            {'name': 'Coke 500ml', 'sub': 'Soda', 'price': 70, 'cost': 55, 'sku': 'JM-L008', 'img': '🥤'},
            {'name': 'Sprite 500ml', 'sub': 'Soda', 'price': 70, 'cost': 55, 'sku': 'JM-L009', 'img': '🥤'},
            {'name': 'Fanta Orange 500ml', 'sub': 'Soda', 'price': 70, 'cost': 55, 'sku': 'JM-L010', 'img': '🥤'},
            {'name': 'Keringet Water 500ml', 'sub': 'Water', 'price': 50, 'cost': 35, 'sku': 'JM-L011', 'img': '💧'},
            {'name': 'Monster Energy 500ml', 'sub': 'Energy Drinks', 'price': 250, 'cost': 180, 'sku': 'JM-L012', 'img': '⚡'},
        ]

        for p_data in liquor_list:
            sub = subcats[p_data['sub']]
            is_kadogo = p_data.get('kadogo', False)
            
            prod, created = Product.objects.get_or_create(
                name=p_data['name'],
                defaults={
                    'subcategory': sub,
                    'base_unit_price': Decimal(str(p_data['price'])),
                    'cost_price': Decimal(str(p_data['cost'])),
                    'sku': p_data['sku'],
                    'image': p_data['img'],
                    'stock_qty': Decimal('0') if is_kadogo else Decimal('12'),
                    'whole_unit_stock': 12 if is_kadogo else 0,
                    'created_by': admin,
                    'base_unit_label': 'Bottle',
                    'is_kadogo': is_kadogo,
                    'whole_unit_label': 'Bottle' if is_kadogo else 'Unit'
                }
            )
            
            if created and is_kadogo:
                FragmentSize.objects.create(
                    product=prod,
                    name='Peg (30ml)',
                    fragment_count=25,
                    fragment_price=Decimal(str(round(p_data['price'] / 20))), # Approx price per peg
                    is_default=True
                )
            
            if created:
                self.stdout.write(f"Created Liquor: {prod.name} (Kadogo: {is_kadogo})")

        self.stdout.write(self.style.SUCCESS("Jimmy Mini Mart Seed completed successfully."))
