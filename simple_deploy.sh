#!/bin/bash
set -x
git config user.email "bethwel@quidpath.com"
git config user.name "Bethwel Kimutai"
git checkout master
git pull origin master
git add -A
git status
git commit -m "fix: Update network configuration to auto-create prod_quidpath_network" || echo "No changes or commit failed"
git push origin master
