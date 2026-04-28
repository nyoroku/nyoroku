# payroll/management/commands/setup_tax_rules.py

from django.core.management.base import BaseCommand
from payroll.models import TaxDeductionRule


class Command(BaseCommand):
    help = 'Set up default tax deduction rules for Kenya (PAYE, NHIF, NSSF, etc.)'

    def handle(self, *args, **options):
        # Create default Kenyan tax rules
        tax_rules = [
            {
                'name': 'PAYE',
                'percentage_rate': 30.00,  # This is simplified - real PAYE has tax bands
                'calculation_base': TaxDeductionRule.CalculationBase.GROSS_PAY,
                'description': 'Pay As You Earn Income Tax'
            },
            {
                'name': 'NHIF',
                'percentage_rate': 1.70,  # This is simplified - real NHIF has contribution bands
                'calculation_base': TaxDeductionRule.CalculationBase.GROSS_PAY,
                'description': 'National Hospital Insurance Fund'
            },
            {
                'name': 'NSSF',
                'percentage_rate': 6.00,
                'calculation_base': TaxDeductionRule.CalculationBase.BASIC_SALARY,
                'description': 'National Social Security Fund'
            },
            {
                'name': 'Housing Levy',
                'percentage_rate': 1.50,
                'calculation_base': TaxDeductionRule.CalculationBase.GROSS_PAY,
                'description': 'Affordable Housing Levy'
            },
        ]

        created_count = 0
        updated_count = 0

        for rule_data in tax_rules:
            rule, created = TaxDeductionRule.objects.get_or_create(
                name=rule_data['name'],
                defaults=rule_data
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created tax rule: {rule.name}')
                )
            else:
                # Update existing rule
                for key, value in rule_data.items():
                    setattr(rule, key, value)
                rule.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Updated tax rule: {rule.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Setup complete. Created: {created_count}, Updated: {updated_count} tax rules.'
            )
        )