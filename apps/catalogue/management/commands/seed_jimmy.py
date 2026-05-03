from django.core.management.base import BaseCommand
from catalogue.models import Category, SubCategory, Product, FragmentSize
from accounts.models import User
from decimal import Decimal
import re
from django.db import IntegrityError

class Command(BaseCommand):
    help = 'Seeds the database with ALL Jimmy Mini Mart items from the provided price list'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting Comprehensive Jimmy Mini Mart seed...")
        
        admin = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not admin:
            self.stdout.write(self.style.ERROR("Error: No user found."))
            return

        # 1. Categories Mapping
        categories_config = {
            'Airtime': ('📱', ['Airtel', 'Safaricom']),
            'Stationery': ('✏️', ['Ex. Book', 'Pen', 'Pencil', 'Eraser', 'Ruler', 'Geo. Set', 'Envelope', 'File', 'Ink', 'Calculator', 'Clip Board']),
            'Food Staples': ('🍚', ['Sugar', 'Salt', 'Rice', 'Flour', 'Ngano', 'Cooking Oil', 'Cooking Fat', 'Spaghetti', 'Indomie', 'Sossi', 'Seasoning', 'Royco', 'Onga', 'Curry', 'M.M.']),
            'Beverages': ('☕', ['Tea', 'Coffee', 'Cocoa', 'Milo', 'Nescafe', 'Bevrg']),
            'Drinks': ('🥤', ['Soda', 'Juice', 'Water', 'Energy Drink', 'Predator']),
            'Dairy & Bakery': ('🍞', ['Milk', 'Bread', 'Cakes', 'Mandazi', 'KDF', 'Blueband', 'Yoghurt']),
            'Snacks & Biscuits': ('🍪', ['Biscuit', 'Candy', 'Peanuts', 'Crisps', 'Popcorn', 'Wafers', 'Chocolate Bar']),
            'Personal Care': ('🧴', ['Soap Tab', 'Jelly', 'Lotion', 'Tooth Paste', 'Tooth Brush', 'Pads', 'Diapers', 'Razor', 'Cutex', 'Perfume', 'Ear Buds', 'Glycerine', 'Hair', 'Condom', 'Trust']),
            'Household': ('🏠', ['Battery', 'Bulb', 'Matchbox', 'Candle', 'Torch', 'Padlock', 'Rope', 'Tape', 'Glue', 'Nail Cutter', 'File Spring']),
            'Cleaning Supplies': ('🧼', ['Soap Powder', 'Soap Bar', 'Bleach', 'JIK', 'Scrubber', 'Broom', 'Brush', 'Downy', 'Starsoft']),
            'Kitchenware': ('🍳', ['Grater', 'Lunch Box', 'Sieve', 'Tumbler', 'Mwiko', 'Feeding Bottle']),
            'Tools & Sewing': ('🧵', ['Needle', 'Thread', 'Wool', 'Crochet', 'Knitting']),
            'Medicines': ('💊', ['Meds', 'Panadol', 'Maramoja', 'Actal', 'ENO', 'Diclofenac', 'Cetrizine']),
            'Bags & Packaging': ('🛍️', ['Bag', 'Carrier', 'Sack', 'Onion Net', 'Alum. Foil', 'Cling Film']),
            'Miscellaneous': ('📦', ['Miscellaneous', 'Phone Charging', 'Pressure', 'Jerry Can']),
        }

        cats = {}
        subcats = {}
        for cat_name, (icon, subs) in categories_config.items():
            cat, _ = Category.objects.get_or_create(name=cat_name, defaults={'icon': icon})
            cats[cat_name] = cat
            for sub_name in subs:
                sub, _ = SubCategory.objects.get_or_create(category=cat, name=sub_name)
                subcats[sub_name] = sub

        general_sub, _ = SubCategory.objects.get_or_create(category=cats['Miscellaneous'], name='General')

        # 2. Raw Price List Data
        raw_items = [
            ('AIRTIME AIRTEL (10)', 'Airtime', 'Airtel', 10),
            ('AIRTIME AIRTEL (20)', 'Airtime', 'Airtel', 20),
            ('AIRTIME AIRTEL (50)', 'Airtime', 'Airtel', 50),
            ('AIRTIME AIRTEL (100)', 'Airtime', 'Airtel', 100),
            ('AIRTIME SAFARICOM (10)', 'Airtime', 'Safaricom', 10),
            ('AIRTIME SAFARICOM (20)', 'Airtime', 'Safaricom', 20),
            ('AIRTIME SAFARICOM (50)', 'Airtime', 'Safaricom', 50),
            ('AIRTIME SAFARICOM (100)', 'Airtime', 'Safaricom', 100),
            ('ALLUM. FOIL 5M', 'Bags & Packaging', 'Alum. Foil', 180),
            ('BAGS Nonwoven #15', 'Bags & Packaging', 'Bag', 5),
            ('BATTERY (Eveready) AA', 'Household', 'Battery', 80),
            ('BEVRG. KAHAWA No. 1', 'Beverages', 'Coffee', 30),
            ('BEVRG. NESCAFE 3-IN-1', 'Beverages', 'Nescafe', 25),
            ('BISCUITS Happy Happy', 'Snacks & Biscuits', 'Biscuit', 5),
            ('BISCUITS Nuvita Milk', 'Snacks & Biscuits', 'Biscuit', 5),
            ('BLUEBAND 250g', 'Dairy & Bakery', 'Blueband', 180),
            ('BREAD 400g', 'Dairy & Bakery', 'Bread', 70),
            ('BULB 9W LED', 'Household', 'Bulb', 100),
            ('CANDY TROPICAL Mints', 'Snacks & Biscuits', 'Candy', 3.33, 3, 10),
            ('CANDY TROPICAL Mints 1pc', 'Snacks & Biscuits', 'Candy', 5),
            ('COOKING OIL Salit 1L', 'Food Staples', 'Cooking Oil', 300),
            ('DIAPERS Softcare Jumbo Pcs', 'Personal Care', 'Diapers', 20),
            ('Ex. BOOK A5 80pgs', 'Stationery', 'Ex. Book', 40),
            ('Ex. COUNTER BK 3Q', 'Stationery', 'Ex. Book', 250),
            ('INDOMIE CHICKEN', 'Food Staples', 'Indomie', 45),
            ('JELLY Arimis 200ml', 'Personal Care', 'Jelly', 130),
            ('JUICE AFIA 500ml', 'Drinks', 'Juice', 80),
            ('KABRAS SUGAR 1kg', 'Food Staples', 'Sugar', 160),
            ('MATCHBOX', 'Household', 'Matchbox', 5),
            ('MEDS Panadol Extra', 'Medicines', 'Panadol', 20),
            ('MILK Fresh 500ml', 'Dairy & Bakery', 'Milk', 60),
            ('NGANO AJAB 2kg', 'Food Staples', 'Flour', 195),
            ('PADS ALWAYS', 'Personal Care', 'Pads', 80),
            ('PEN BIRO BIC', 'Stationery', 'Pen', 25),
            ('RICE PISHORI 1kg', 'Food Staples', 'Rice', 200),
            ('SALT 1kg', 'Food Staples', 'Salt', 40),
            ('SNACKS POTATO Crisps', 'Snacks & Biscuits', 'Crisps', 20),
            ('SOAP Powder TOSS 500g', 'Cleaning Supplies', 'Soap Powder', 200),
            ('SOAP Tab GEISHA 200g', 'Personal Care', 'Soap Tab', 130),
            ('SODA PET 500ml', 'Drinks', 'Soda', 80),
            ('TEA LEAVES NDIMA 240g', 'Beverages', 'Tea', 140),
            ('TISSUE TOILEX', 'Cleaning Supplies', 'General', 40),
            ('TOOTH PASTE COLGATE 140g', 'Personal Care', 'Tooth Paste', 320),
            ('WATER DASANI 500ml', 'Drinks', 'Water', 45),
            ('YOGHURT 500ml', 'Dairy & Bakery', 'Yoghurt', 100),
        ]

        def get_sub(cat_name, item_name):
            possible_subs = categories_config[cat_name][1]
            for s in possible_subs:
                if s.lower() in item_name.lower():
                    return subcats[s]
            return general_sub

        for i, p_data in enumerate(raw_items):
            name = p_data[0]
            cat_name = p_data[1]
            price = Decimal(str(p_data[3]))
            sku = "JM-" + re.sub(r'[^A-Z0-9]', '', name.upper())[:10] + str(i).zfill(3)
            
            bundle_qty = p_data[4] if len(p_data) > 4 else 1
            bundle_price = Decimal(str(p_data[5])) if len(p_data) > 5 else Decimal('0.00')

            sub = get_sub(cat_name, name)
            
            # Using SKU for lookup and handling potential name collisions
            try:
                Product.objects.update_or_create(
                    sku=sku,
                    defaults={
                        'name': name,
                        'subcategory': sub,
                        'base_unit_price': price,
                        'cost_price': price * Decimal('0.85'),
                        'image': categories_config[cat_name][0],
                        'created_by': admin,
                        'stock_qty': Decimal('100'),
                        'bundle_pricing_enabled': (bundle_qty > 1),
                        'bundle_qty': bundle_qty,
                        'bundle_price': bundle_price,
                        'allow_single_sale': True,
                        'single_unit_price': price
                    }
                )
                self.stdout.write(f"Processed: {name}")
            except IntegrityError:
                # If name collides, modify name slightly
                new_name = f"{name} ({sku})"
                Product.objects.update_or_create(
                    sku=sku,
                    defaults={
                        'name': new_name,
                        'subcategory': sub,
                        'base_unit_price': price,
                        'cost_price': price * Decimal('0.85'),
                        'image': categories_config[cat_name][0],
                        'created_by': admin,
                        'stock_qty': Decimal('100'),
                        'bundle_pricing_enabled': (bundle_qty > 1),
                        'bundle_qty': bundle_qty,
                        'bundle_price': bundle_price,
                        'allow_single_sale': True,
                        'single_unit_price': price
                    }
                )
                self.stdout.write(self.style.WARNING(f"Name collision! Created as: {new_name}"))

        self.stdout.write(self.style.SUCCESS("Comprehensive Jimmy Mini Mart Seed completed successfully."))
