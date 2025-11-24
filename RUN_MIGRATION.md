# How to Apply the Truth Report Migration

## ✅ Migration File Created

I've created the migration file:
- **File**: `Tazama/migrations/0004_tazamaanalysisrequest_truth_report.py`
- **What it does**: Adds the `truth_report` JSONField to the database

---

## 🚀 Run This Command

### Option 1: If Docker is running
```bash
docker-compose exec django-backend-dev python manage.py migrate Tazama
```

### Option 2: Restart Docker (applies migrations automatically)
```bash
docker-compose restart django-backend-dev
```

### Option 3: If you need to rebuild
```bash
docker-compose down
docker-compose up -d
```

---

## ✅ After Running Migration

The error will be fixed and you should see:

```
✅ Applying Tazama.0004_tazamaanalysisrequest_truth_report... OK
```

Then try uploading your financial statement again!

---

## 📊 What You'll See Next

After the migration, when you upload the High Risk statement, you'll see:

```
🚨 CRITICAL ALERTS - IMMEDIATE ACTION REQUIRED

1. 🚨 IMMEDIATE CASH CRISIS
   Net income: KES 3,635,000 (profit margin 7.3%)
   
2. HIGH COST RATIO  
   COGS is 73.9% of revenue (KES 37,000,000 / KES 50,050,000)
   Target: 50-60%. Renegotiate supplier contracts.
   
3. EXCESSIVE OPERATING EXPENSES
   OpEx is 18.4% of revenue (KES 9,200,000)
   Target: 25-30% maximum.
```

**All with SPECIFIC numbers from YOUR statement!** 🎯


