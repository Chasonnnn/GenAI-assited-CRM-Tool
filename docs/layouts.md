# UI Design System & Layouts

> Comprehensive design guidelines for consistent UI development

## Theme & Colors

### Color Palette

**Base:** Stone (warm gray)  
**Primary:** Teal (#14b8a6 / Teal-500)

| Token | Light Mode | Dark Mode | Usage |
|-------|-----------|-----------|-------|
| `--background` | Stone-50 | oklch(0.20) | Page background |
| `--foreground` | Stone-950 | Warm stone | Primary text |
| `--card` | White | Slightly lighter | Card backgrounds |
| `--primary` | Teal-500 | Brighter Teal | Buttons, links, accents |
| `--secondary` | Stone-100 | Teal-tinted | Secondary buttons |
| `--muted` | Stone-100 | Warm stone | Muted backgrounds |
| `--muted-foreground` | Stone-500 | Light stone | Secondary text |
| `--destructive` | Red-500 | Red-500 | Error states, delete actions |
| `--border` | Stone-200 | Stone-700 | Borders, dividers |

### Entity Colors

| Entity | Color | Tailwind | Hex |
|--------|-------|----------|-----|
| Surrogate | Purple | `purple-500` | #a855f7 |
| Intended Parent | Green | `green-500` | #22c55e |
| Appointment | Blue | `blue-500` | #3b82f6 |
| Task | Teal | `primary` | #14b8a6 |

### Status Colors

| Status | Background | Text | Border |
|--------|-----------|------|--------|
| Pending | `yellow-500/10` | `yellow-600` | `yellow-500/20` |
| Confirmed | `green-500/10` | `green-600` | `green-500/20` |
| Completed | `blue-500/10` | `blue-600` | `blue-500/20` |
| Cancelled | `red-500/10` | `red-600` | `red-500/20` |
| Expired | `gray-500/10` | `gray-600` | `gray-500/20` |

---

## Typography

### Font Families

```css
--font-sans: "Noto Sans", system-ui, sans-serif;
--font-mono: "Geist Mono", monospace;
```

### Font Sizes

| Name | Size | Line Height | Usage |
|------|------|-------------|-------|
| `text-xs` | 12px | 16px | Labels, badges, captions |
| `text-sm` | 14px | 20px | Body text, form labels |
| `text-base` | 16px | 24px | Default body text |
| `text-lg` | 18px | 28px | Section titles in cards |
| `text-xl` | 20px | 28px | Page titles (compact) |
| `text-2xl` | 24px | 32px | Main page titles |
| `text-3xl` | 30px | 36px | Dashboard metrics |

### Font Weights

| Weight | Class | Usage |
|--------|-------|-------|
| 400 | `font-normal` | Body text |
| 500 | `font-medium` | Labels, nav items |
| 600 | `font-semibold` | Headings, buttons |
| 700 | `font-bold` | Important headings |

---

## Spacing & Layout

### Spacing Scale

| Class | Size | Usage |
|-------|------|-------|
| `gap-1` | 4px | Icon spacing |
| `gap-2` | 8px | Button icon + text |
| `gap-3` | 12px | Form fields |
| `gap-4` | 16px | Card sections |
| `gap-6` | 24px | Page sections |

### Page Layout

```tsx
// Standard page structure
<div className="flex min-h-screen flex-col">
    {/* Page Header - h-12 to h-14 */}
    <div className="border-b border-border bg-background/95 backdrop-blur">
        <div className="flex h-14 items-center justify-between px-6">
            <h1 className="text-xl font-semibold">Page Title</h1>
            {/* Actions */}
        </div>
    </div>

    {/* Main Content */}
    <div className="flex-1 p-6 space-y-4">
        {/* Content */}
    </div>
</div>
```

### Header Heights

| Context | Height | Title Size |
|---------|--------|------------|
| Compact pages | `h-12` | `text-base` |
| Standard pages | `h-14` | `text-xl` |
| Feature pages | `h-16` | `text-2xl` |

---

## Components

### Buttons

| Variant | Class | Usage |
|---------|-------|-------|
| Primary | `variant="default"` | Main actions |
| Secondary | `variant="secondary"` | Alternative actions |
| Outline | `variant="outline"` | Tertiary actions |
| Ghost | `variant="ghost"` | Icon buttons, subtle actions |
| Destructive | `variant="destructive"` | Delete, cancel |

**Sizes:**
- `size="sm"` + `h-7` + `text-xs`: Compact UI, table actions
- `size="sm"` + `h-8`: Standard small
- `size="default"`: Standard
- `size="lg"`: Primary CTAs

### Badges

```tsx
// Status badges
<Badge className={STATUS_COLORS[status]}>
    {label}
</Badge>

// Outline badges
<Badge variant="outline" className="text-xs px-1.5 py-0">
    Label
</Badge>
```

### Cards

```tsx
<Card>
    <CardHeader>
        <CardTitle className="text-lg">Title</CardTitle>
        <CardDescription>Description</CardDescription>
    </CardHeader>
    <CardContent className="space-y-4">
        {/* Content */}
    </CardContent>
</Card>
```

### Tabs

```tsx
<Tabs defaultValue="tab1">
    <TabsList>
        <TabsTrigger value="tab1">Tab 1</TabsTrigger>
        <TabsTrigger value="tab2">Tab 2</TabsTrigger>
    </TabsList>
    <TabsContent value="tab1" className="mt-4">
        {/* Content */}
    </TabsContent>
</Tabs>
```

---

## Border Radius

```css
--radius: 0.5rem; /* 8px base */
```

| Token | Size | Usage |
|-------|------|-------|
| `rounded-sm` | 4px | Small elements |
| `rounded-md` | 6px | Buttons, inputs |
| `rounded-lg` | 8px | Cards, dialogs |
| `rounded-xl` | 12px | Large cards |
| `rounded-full` | 9999px | Avatars, pills |

---

## Icons

**Library:** Lucide React

**Standard sizes:**
- `size-3` (12px): Inline with text-xs
- `size-3.5` (14px): Inline with text-sm
- `size-4` (16px): Standard buttons
- `size-5` (20px): Feature icons
- `size-8` (32px): Empty states
- `size-12` (48px): Large empty states

---

## Patterns

### Empty States

```tsx
<div className="text-center py-12">
    <AlertCircleIcon className="size-12 mx-auto mb-4 text-muted-foreground/50" />
    <p className="text-muted-foreground">No items found</p>
</div>
```

### Loading States

```tsx
<div className="flex items-center justify-center py-12">
    <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
</div>
```

### List Items

```tsx
<div className="p-4 rounded-lg border border-border hover:bg-muted/50 cursor-pointer transition-colors">
    <div className="flex items-center gap-4">
        <Avatar className="size-12" />
        <div className="flex-1 min-w-0">
            <h4 className="font-medium truncate">Title</h4>
            <p className="text-sm text-muted-foreground">Subtitle</p>
        </div>
        <ChevronRightIcon className="size-5 text-muted-foreground" />
    </div>
</div>
```

---

## Responsive Breakpoints

| Breakpoint | Size | Usage |
|------------|------|-------|
| `sm:` | 640px | Mobile landscape |
| `md:` | 768px | Tablet |
| `lg:` | 1024px | Desktop |
| `xl:` | 1280px | Large desktop |
| `2xl:` | 1536px | Wide screens |

---

## Dark Mode

All components support dark mode via CSS variables. The theme toggle uses View Transition API with a circle animation.

```tsx
// Theme is managed via ThemeProvider
<ThemeProvider attribute="class" defaultTheme="system" enableSystem>
    {children}
</ThemeProvider>
```
