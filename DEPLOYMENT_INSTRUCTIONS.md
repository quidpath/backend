# Deployment Instructions

## Quick Start

Run this single command to commit and push all changes:

```bash
chmod +x DEPLOY_ALL_SERVICES.sh
./DEPLOY_ALL_SERVICES.sh
```

This will:
1. ✅ Commit changes to Development branch
2. ✅ Push to Development (no deployment triggered)
3. ✅ Prepare for production deployment

## Step-by-Step Manual Process

### Step 1: Commit to Development Branch

#### Backend Repository
```bash
cd backend
git checkout Development
git add -A
git commit -m "fix: Disable stage deployments and fix network configuration"
git push origin Development
```

#### Inventory Repository
```bash
cd inventory
git checkout Development
git add -A
git commit -m "fix: Disable stage deployments and fix network configuration"
git push origin Development
```

### Step 2: Create Pull Requests (GitHub UI)

1. **Go to Backend Repository on GitHub**
   - Click "Pull requests" tab
   - Click "New pull request"
   - Base: `master` ← Compare: `Development`
   - Click "Create pull request"
   - Add title: "Deploy: Fix network configuration and disable stage"
   - Click "Create pull request"

2. **Go to Inventory Repository on GitHub**
   - Repeat the same process

### Step 3: Merge Pull Requests

1. Review the changes in each PR
2. Click "Merge pull request"
3. Click "Confirm merge"
4. **Production deployment will trigger automatically**

## Alternative: Direct Merge (Command Line)

If you want to skip the PR process:

### Backend
```bash
cd backend
git checkout master
git pull origin master
git merge Development
git push origin master
```

### Inventory
```bash
cd inventory
git checkout master
git pull origin master
git merge Development
git push origin master
```

## What Happens After Merge to Master

### Automatic Actions:
1. ✅ GitHub Actions workflow triggers
2. ✅ Docker images built with `prod-<timestamp>` tag
3. ✅ Images pushed to Docker Hub
4. ✅ Deployment triggered to production servers
5. ✅ `prod_quidpath_network` created automatically (if doesn't exist)
6. ✅ All services deployed and connected
7. ✅ Services can communicate via shared network

### Expected Results:
- ✅ Backend deployed to production
- ✅ Inventory deployed to production
- ✅ Network created automatically
- ✅ All services can communicate
- ✅ POS integration works
- ✅ No manual network creation needed

## Verification After Deployment

### Check GitHub Actions
1. Go to repository → Actions tab
2. Look for the latest workflow run
3. Ensure it shows green checkmark ✅

### Check Production Server (Optional)
```bash
ssh ubuntu@production-server

# Check containers are running
docker ps | grep prod

# Check network exists
docker network ls | grep prod_quidpath_network

# Check network connectivity
docker network inspect prod_quidpath_network

# Check logs
docker logs quidpath-backend-prod --tail 50
docker logs inventory-backend --tail 50
```

## Changes Summary

### Files Modified:

#### Backend
- `.github/workflows/deploy.yml` - Only triggers on master
- `docker-compose.yml` - Uses `prod_quidpath_network` (non-external)
- `docker-compose.stage.yml` - Uses `stage_quidpath_network` (non-external)
- `scripts/ensure-network.sh` - Helper script (created)

#### Inventory
- `.github/workflows/deploy-stage.yml` - DISABLED
- `docker-compose.yml` - Uses `prod_quidpath_network` (non-external)
- `docker-compose.stage.yml` - Uses `stage_quidpath_network` (non-external)
- `scripts/ensure-network.sh` - Helper script (created)

#### Other Services
- All `deploy-stage.yml` workflows - DISABLED
- No code changes needed
- Will deploy normally on master push

## Troubleshooting

### If commit fails:
```bash
# Check what changed
git status

# Check if you're on the right branch
git branch

# Try committing again
git add -A
git commit -m "fix: Network configuration"
```

### If push fails:
```bash
# Set upstream if needed
git push --set-upstream origin Development

# Or force push (use carefully)
git push -f origin Development
```

### If merge conflicts:
```bash
# Pull latest master
git checkout master
git pull origin master

# Merge Development
git merge Development

# Resolve conflicts in your editor
# Then:
git add -A
git commit -m "Merge Development into master"
git push origin master
```

## Important Notes

1. **Development branch push = No deployment** ✅
2. **Master branch push = Production deployment** ✅
3. **Stage deployments are disabled** ✅
4. **Networks auto-create on deployment** ✅
5. **No manual intervention needed** ✅

## Timeline

- **Commit & Push to Development:** 2 minutes
- **Create & Merge PR:** 3 minutes
- **Deployment to Production:** 5-10 minutes
- **Total:** ~15 minutes

## Support

If you encounter issues:

1. Check GitHub Actions logs
2. Check Docker container logs
3. Verify network exists: `docker network ls`
4. Review `DEPLOYMENT_CHANGES_SUMMARY.md`
5. Check `COMPLETE_FIX_GUIDE.md` in inventory folder

## Next Steps After Deployment

1. ✅ Verify production is running
2. ✅ Test POS integration
3. ✅ Check all services can communicate
4. ✅ Monitor logs for any errors
5. ✅ Celebrate! 🎉
