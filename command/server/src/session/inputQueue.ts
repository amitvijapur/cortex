// Cortex Command — streaming-input queue.
//
// The Agent SDK's `query({ prompt })` accepts an AsyncIterable<SDKUserMessage>
// for multi-turn: each yielded message is a new turn without recreating the
// query (and without re-booting the runtime child). This queue lets the server
// push user turns on demand — `push()` feeds the async iterator the SDK is
// draining; `close()` ends the conversation so the runtime child is reaped.

import type { SDKUserMessage } from "@anthropic-ai/claude-agent-sdk";

export class InputQueue implements AsyncIterable<SDKUserMessage> {
  private items: SDKUserMessage[] = [];
  private waiters: Array<(r: IteratorResult<SDKUserMessage>) => void> = [];
  private closed = false;

  push(message: SDKUserMessage): void {
    if (this.closed) return;
    const waiter = this.waiters.shift();
    if (waiter) {
      waiter({ value: message, done: false });
    } else {
      this.items.push(message);
    }
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    let waiter = this.waiters.shift();
    while (waiter) {
      waiter({ value: undefined, done: true } as IteratorResult<SDKUserMessage>);
      waiter = this.waiters.shift();
    }
  }

  async *[Symbol.asyncIterator](): AsyncIterator<SDKUserMessage> {
    while (true) {
      const item = this.items.shift();
      if (item !== undefined) {
        yield item;
        continue;
      }
      if (this.closed) return;
      const next = await new Promise<IteratorResult<SDKUserMessage>>((resolve) => {
        this.waiters.push(resolve);
      });
      if (next.done) return;
      yield next.value;
    }
  }
}
