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
