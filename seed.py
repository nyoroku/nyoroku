from accounts.models import User
from catalogue.models import Category, SubCategory, Product
from core.models import log_audit
from decimal import Decimal

# Ensure admin user exists
admin = User.objects.filter(username='admin').first()

# Categories
groceries = Category.objects.create(name='Groceries', icon='🥬')
personal_care = Category.objects.create(name='Personal Care', icon='🧴')
meat = Category.objects.create(name='Meat & Poultry', icon='🥩')
bakery = Category.objects.create(name='Bakery', icon='🍞')
snacks = Category.objects.create(name='Snacks & Drinks', icon='🧃')

# Subcategories
staples = SubCategory.objects.create(category=groceries, name='Staples')
dairy = SubCategory.objects.create(category=groceries, name='Dairy')

soap = SubCategory.objects.create(category=personal_care, name='Soap & Wash')

beef = SubCategory.objects.create(category=meat, name='Beef')
chicken = SubCategory.objects.create(category=meat, name='Chicken')

bread = SubCategory.objects.create(category=bakery, name='Bread')

sweets = SubCategory.objects.create(category=snacks, name='Sweets')
soda = SubCategory.objects.create(category=snacks, name='Soda')

# Standard Products (Whole sell)
Product.objects.create(
    name='Supa Loaf Bread 400g',
    subcategory=bread,
    base_unit_price=Decimal('65'),
    cost_price=Decimal('50'),
    stock_qty=Decimal('20'),
    image='🍞',
    sku='P-001',
)

Product.objects.create(
    name='Coca Cola 500ml',
    subcategory=soda,
    base_unit_price=Decimal('65'),
    cost_price=Decimal('50'),
    stock_qty=Decimal('48'),
    image='🥤',
    sku='P-002',
)

# Split Sell Product
Product.objects.create(
    name='Geisha Soap (Pack of 4)',
    subcategory=soap,
    base_unit_price=Decimal('500'),
    cost_price=Decimal('400'),
    stock_qty=Decimal('10'),
    split_enabled=True,
    split_unit_label='Piece',
    split_unit_price=Decimal('135'),
    pieces_per_base=4,
    split_inventory_mode='virtual',
    image='🧼',
    sku='P-003',
)

# Weight Sell Product
Product.objects.create(
    name='Premium Beef Steak',
    subcategory=beef,
    base_unit_price=Decimal('600'), # Price per 1KG
    base_unit_label='1kg',
    cost_price=Decimal('450'),
    weight_sell_enabled=True,
    weight_unit='kg',
    price_per_weight_unit=Decimal('600'),
    stock_in_weight_unit=Decimal('12.5'),
    weight_sell_mode='BY_WEIGHT',
    image='🥩',
    sku='P-004',
)

Product.objects.create(
    name='Kabras Sugar',
    subcategory=staples,
    base_unit_price=Decimal('180'), # Price per 1KG
    cost_price=Decimal('150'),
    weight_sell_enabled=True,
    weight_unit='kg',
    price_per_weight_unit=Decimal('180'),
    stock_in_weight_unit=Decimal('50.0'),
    weight_sell_mode='BY_CASH',
    image='🍚',
    sku='P-005',
)

# Bunch Sell Product
Product.objects.create(
    name='Tropical Mints',
    subcategory=sweets,
    base_unit_price=Decimal('250'), # Whole pack price
    cost_price=Decimal('180'),
    stock_qty=Decimal('5'),
    bunch_enabled=True,
    bunch_qty=3,
    bunch_price=Decimal('5'),
    single_price=Decimal('2'),
    image='🍬',
    sku='P-006',
)

print('Seed data created successfully.')
