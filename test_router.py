import sys
sys.path.insert(0, '.')

from api.worktree_routes import router

print(f'Router has {len(router.routes)} routes')
for route in router.routes:
    print(f'  - {route.methods} {route.path}')
