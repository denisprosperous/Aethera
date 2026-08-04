/**
 * LLM API Route — uses the built-in z-ai-web-dev-sdk (GLM-5.2).
 * No API key required — the SDK authenticates through the platform.
 *
 * POST /api/llm
 * Body: { prompt: string, systemPrompt?: string }
 * Returns: { text: string, provider: string, success: boolean }
 */

import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const maxDuration = 30;

export async function POST(req: NextRequest) {
  try {
    const { prompt, systemPrompt } = await req.json();
    if (!prompt) {
      return NextResponse.json({ error: 'prompt is required' }, { status: 400 });
    }

    // Use the built-in Z.ai SDK (no API key needed).
    const ZAI = (await import('z-ai-web-dev-sdk')).default;
    const zai = await ZAI.create();

    const messages: Array<{ role: 'assistant' | 'user' | 'system'; content: string }> = [
      { role: 'assistant', content: systemPrompt || 'You are AETHERA, a helpful assistant for a geometric analysis platform. Answer clearly and concisely.' },
      { role: 'user', content: prompt },
    ];

    const completion = await zai.chat.completions.create({
      messages,
      thinking: { type: 'disabled' },
    });

    const text = completion.choices[0]?.message?.content || '';

    return NextResponse.json({
      text,
      provider: 'GLM-5.2 (Z.ai)',
      success: true,
    });
  } catch (error: any) {
    return NextResponse.json({
      text: `LLM error: ${error.message}`,
      provider: 'none',
      success: false,
      error: error.message,
    }, { status: 500 });
  }
}

export async function GET() {
  return NextResponse.json({
    primary: 'GLM-5.2 (Z.ai built-in SDK)',
    configured: true,
    note: 'The z-ai-web-dev-sdk authenticates through the platform — no API key required.',
  });
}
