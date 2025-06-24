# DevHex Pipeline Launcher — Frontend

A modern Vite + React + Tailwind CSS frontend for the DevHex Pipeline Launcher.

## Features

- Vite-powered fast development
- React 18
- Tailwind CSS for styling
- Cross-platform: Linux, Windows, macOS

---

## Prerequisites

- **Node.js** (v18+ recommended)
- **npm** or **pnpm**

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/HexlerHolding/devops-automation.git
cd devops-automation/next_frontend
```

### 2. Install Dependencies

#### macOS & Linux
```bash
npm install
# or
pnpm install
```

#### Windows
```cmd
npm install
:: or
pnpm install
```

---

## Running the Frontend

### macOS & Linux
```bash
npm run dev
# or
pnpm run dev
```

### Windows
```cmd
npm run dev
:: or
pnpm run dev
```

- The app will be available at [http://localhost:5173](http://localhost:5173) (or another port if 5173 is in use).

---

## Building for Production

### macOS & Linux
```bash
npm run build
# or
pnpm run build
```

### Windows
```cmd
npm run build
:: or
pnpm run build
```

To preview the production build locally:

#### macOS & Linux
```bash
npm run preview
# or
pnpm run preview
```

#### Windows
```cmd
npm run preview
:: or
pnpm run preview
```

---

## Troubleshooting

- If you see errors related to PostCSS or Tailwind CSS, ensure your `postcss.config.js` looks like this:
  ```js
  module.exports = {
    plugins: {
      tailwindcss: {},
      autoprefixer: {},
    },
  };
  ```
- If ports are in use, either stop the conflicting process or use a different port.

---

## License

See [LICENSE](../LICENSE). 