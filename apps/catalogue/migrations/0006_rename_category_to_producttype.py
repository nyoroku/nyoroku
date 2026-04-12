from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0005_remove_product_barcode_remove_productvariant_barcode'),
    ]

    operations = [
        # Step 1: Remove the constraint that references 'parent' BEFORE removing parent
        migrations.RemoveConstraint(
            model_name='category',
            name='unique_category_per_parent',
        ),
        # Step 2: Remove the 'parent' field (subcategory support)
        migrations.RemoveField(
            model_name='category',
            name='parent',
        ),
        # Step 3: Rename Category model to ProductType
        migrations.RenameModel(
            old_name='Category',
            new_name='ProductType',
        ),
        # Step 4: Rename Product.category field to Product.product_type
        migrations.RenameField(
            model_name='product',
            old_name='category',
            new_name='product_type',
        ),
        # Step 5: Make name unique on its own
        migrations.AlterField(
            model_name='producttype',
            name='name',
            field=models.CharField(max_length=50, unique=True),
        ),
        # Step 6: Update verbose_name_plural
        migrations.AlterModelOptions(
            name='producttype',
            options={'ordering': ['name'], 'verbose_name_plural': 'Product Types'},
        ),
    ]
