# QuidPath Multi-Service Deployment

This directory contains the main backend service and deployment scripts for the entire QuidPath ecosystem.

## Quick Start

### Windows Users

Run the master control panel:
```batch
..\quidpath-control.bat
```

Or deploy directly:
```batch
..\deploy-all-production.bat
```

### Linux/Mac Users

```bash
chmod +x ../deploy-all-production.sh
sudo ../deploy-all-production.sh
```

## What's Included

This deployment manages three interconnected services:

1. **Main Backend** (this directory) - Port 8000
2. **Billing Microservice** (../billing) - Port 8002  
3. **Tazama AI Microservice** (../tazama-ai-microservice) - Port 8001

All services share a single authentication database for unified user management.

## Documentation

- **Full Guide**: See `../DEPLOYMENT-GUIDE.md`
- **Quick Reference**: See `../QUICK-REFERENCE.md`
- **Changes**: See `../CHANGES-SUMMARY.md`

## Default Credentials

- **Username**: admin
- **Password**: admin123

Works for all three admin panels!

## Service URLs

- Main Backend: http://localhost:8000/admin/
- Billing: http://localhost:8002/admin/
- Tazama AI: http://localhost:8001/admin/

## Need Help?

Run the diagnostic tool:
```batch
..\diagnose-issues.bat
```

Or check the comprehensive deployment guide.
