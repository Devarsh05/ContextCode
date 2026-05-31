This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

## API Types

`types/api.d.ts` is generated from the backend's OpenAPI schema with
[`openapi-typescript`](https://openapi-ts.dev) — it is the source of truth for
request/response shapes, so the frontend stays typed against the real backend
contract. **Do not edit it by hand.**

Regenerate it whenever the backend API changes. Start the backend first
(`uvicorn app.main:app --reload` from `/backend`, serving on
`http://localhost:8000`), then run:

```bash
npm run gen:types
```

This reads `http://localhost:8000/openapi.json` and overwrites
`types/api.d.ts`. To point at a different backend, run the CLI directly:

```bash
npx openapi-typescript <url>/openapi.json -o types/api.d.ts
```

Import the generated types in app code, e.g.:

```ts
import type { components } from "@/types/api";

type GraphResponse = components["schemas"]["GraphResponse"];
```

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
