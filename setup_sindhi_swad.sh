#!/bin/bash
# setup_sindhi_swad.sh
# Run: bash setup_sindhi_swad.sh
# Creates Sindhi Swad plugin-based cloud kitchen starter

set -e

ROOT="SindhiSwad"
mkdir -p $ROOT && cd $ROOT

echo "📂 Creating repo structure..."
mkdir -p apps/web apps/api apps/mobile
mkdir -p packages/core packages/plugins/payments-stripe packages/plugins/promotions packages/plugins/delivery-zones
mkdir -p packages/ui packages/config packages/types packages/emails
mkdir -p infra/prisma infra/k8s
touch turbo.json package.json .env.example README.md

echo "📝 Writing package.json..."
cat > package.json <<'EOF'
{
  "name": "sindhi-swad",
  "private": true,
  "packageManager": "pnpm@9.6.0",
  "scripts": {
    "dev:web": "pnpm --filter @sindhiswad/web dev",
    "dev:api": "pnpm --filter @sindhiswad/api start:dev",
    "dev:mobile": "pnpm --filter @sindhiswad/mobile start",
    "dev:all": "turbo run dev",
    "build": "turbo run build",
    "lint": "turbo run lint",
    "test": "turbo run test",
    "db:push": "prisma db push --schema=infra/prisma/schema.prisma",
    "db:migrate": "prisma migrate dev --schema=infra/prisma/schema.prisma",
    "db:studio": "prisma studio --schema=infra/prisma/schema.prisma"
  }
}
EOF

echo "📝 Writing turbo.json..."
cat > turbo.json <<'EOF'
{
  "$schema": "https://turborepo.org/schema.json",
  "pipeline": {
    "build": { "dependsOn": ["^build"], "outputs": ["dist/**", ".next/**"] },
    "dev": { "cache": false },
    "lint": {},
    "test": {}
  }
}
EOF

echo "📝 Writing .env.example..."
cat > .env.example <<'EOF'
NODE_ENV=development
BASE_URL=http://localhost:3001
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sindhiswad
REDIS_URL=redis://localhost:6379

NEXTAUTH_SECRET=changeme
NEXTAUTH_URL=http://localhost:3000

STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=

RESEND_API_KEY=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
FIREBASE_PROJECT_ID=
FIREBASE_CLIENT_EMAIL=
FIREBASE_PRIVATE_KEY=
EOF

echo "📝 Writing Prisma schema..."
cat > infra/prisma/schema.prisma <<'EOF'
generator client { provider = "prisma-client-js" }
datasource db { provider = "postgresql" url = env("DATABASE_URL") }

model User {
  id        String   @id @default(cuid())
  email     String   @unique
  name      String?
  role      UserRole @default(CUSTOMER)
  orders    Order[]
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
}

enum UserRole { CUSTOMER ADMIN KITCHEN_STAFF DELIVERY }

model Order {
  id         String   @id @default(cuid())
  status     String   @default("PENDING_PAYMENT")
  totalCents Int
  currency   String   @default("INR")
  createdAt  DateTime @default(now())
}
EOF

echo "📝 Writing plugin core..."
cat > packages/core/plugin-registry.ts <<'EOF'
export type CoreEvent = { type: string; payload: any }

export interface PluginContext {
  env: Record<string, string | undefined>;
  logger: { info: (...a: any[]) => void; error: (...a: any[]) => void };
}

export interface SindhiSwadPlugin {
  name: string;
  version: string;
  handles?: string[];
  init?(ctx: PluginContext): Promise<void> | void;
  onEvent?(e: CoreEvent, ctx: PluginContext): Promise<void> | void;
}

export class PluginRegistry {
  private plugins: SindhiSwadPlugin[] = []
  constructor(private ctx: PluginContext) {}
  use(p: SindhiSwadPlugin) { this.plugins.push(p); return this; }
  async initAll() { for (const p of this.plugins) await p.init?.(this.ctx); }
  async dispatch(e: CoreEvent) {
    for (const p of this.plugins) if (!p.handles || p.handles.includes(e.type)) await p.onEvent?.(e, this.ctx)
  }
}
EOF

echo "📝 Writing Stripe plugin..."
cat > packages/plugins/payments-stripe/index.ts <<'EOF'
import type { SindhiSwadPlugin, PluginContext, CoreEvent } from "@sindhiswad/core"
export default function stripePlugin(): SindhiSwadPlugin {
  return {
    name: "payments.stripe", version: "1.0.0",
    handles: ["payment.intent.created"],
    async onEvent(e: CoreEvent, ctx: PluginContext) {
      ctx.logger.info("Stripe plugin handling", e)
      // TODO: integrate stripe
    }
  }
}
EOF

echo "✅ Sindhi Swad monorepo structure created."
echo "Next steps:"
echo "  1. cd SindhiSwad"
echo "  2. pnpm i"
echo "  3. docker compose -f infra/docker-compose.yml up -d"
echo "  4. pnpm db:push && pnpm dev:all"
