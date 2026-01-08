# Frontend Expert Query Template

Use this expert when working on:
- Next.js pages and layouts
- React components (Server or Client)
- TypeScript interfaces and types
- Tailwind CSS styling
- shadcn/ui component usage
- Client-side state management
- Real-time WebSocket UI updates

## Query Format

```
Domain: frontend
Task: [describe the UI/component work]
Context: [existing components or pages to reference]
Question: [specific question about implementation]
```

## Example Queries

### Creating a new page
```
Domain: frontend
Task: Create Kanban board page for parallel execution
Context: Similar layout to existing projects/[id]/page.tsx
Question: Should this be a Server Component with Client islands, or full Client Component?
```

### Component design
```
Domain: frontend
Task: Build WorktreeSwimlane component showing agent status
Context: Need real-time updates via WebSocket
Question: How to structure the component for optimal re-renders?
```

## Routing Rules

Route to this expert when:
1. File path contains `web-ui/` or `components/`
2. Task mentions: UI, component, page, React, Next.js, Tailwind
3. Working with user interactions or visual elements
4. Implementing client-side state or effects
