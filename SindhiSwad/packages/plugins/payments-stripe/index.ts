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
