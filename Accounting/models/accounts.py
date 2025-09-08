import uuid

from django.db import models
from OrgAuth.models import Corporate
from quidpath_backend.core.base_models.base import BaseModel


class AccountType(BaseModel):
    name = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'account_type'

    def __str__(self):
        return self.name


class AccountSubType(BaseModel):
    account_type = models.ForeignKey(AccountType, on_delete=models.CASCADE, related_name='sub_types')
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'account_sub_type'

    def __str__(self):
        return f"{self.name} ({self.account_type.name})"


class Account(BaseModel):
    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    account_type = models.ForeignKey(AccountType, on_delete=models.PROTECT, blank=True, null=True)
    account_sub_type = models.ForeignKey(AccountSubType, on_delete=models.PROTECT, blank=True, null=True)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'account'
        unique_together = ('corporate', 'code')

    def __str__(self):
        return f"{self.code} - {self.name} ({self.account_type.name})"

class JournalEntry(BaseModel):
    corporate = models.ForeignKey(Corporate, on_delete=models.CASCADE)
    date = models.DateField()
    reference = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, default='')
    is_posted = models.BooleanField(default=False)

    class Meta:
        db_table = 'journal_entry'
        unique_together = ('corporate', 'reference')

    def __str__(self):
        return f"{self.reference} - {self.date}"


class JournalEntryLine(BaseModel):
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    debit = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    description = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'journal_entry_line'

    def __str__(self):
        return f"{self.journal_entry.reference} - {self.account.name} (Debit: {self.debit}, Credit: {self.credit})"