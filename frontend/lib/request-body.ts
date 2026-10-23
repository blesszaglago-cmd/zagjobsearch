export const MAX_BODY_BYTES = 64 * 1024;

export class RequestBodyError extends Error {
  constructor(
    public readonly status: 400 | 413 | 415,
    message: string,
  ) {
    super(message);
  }
}

export async function boundedBody(request: Request, maximum = MAX_BODY_BYTES) {
  const declared = request.headers.get("content-length");
  if (declared !== null && !/^\d{1,10}$/.test(declared))
    throw new RequestBodyError(400, "Invalid request size.");
  if (declared !== null && Number(declared) > maximum)
    throw new RequestBodyError(413, "Request is too large.");
  const encoding = request.headers.get("content-encoding");
  if (encoding && encoding.toLowerCase() !== "identity")
    throw new RequestBodyError(
      415,
      "Compressed request bodies are not accepted.",
    );
  if (!request.body) return new Uint8Array();
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maximum) {
        await reader.cancel();
        throw new RequestBodyError(413, "Request is too large.");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return bytes;
}
