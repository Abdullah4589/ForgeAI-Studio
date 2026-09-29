/** Build a minimal, valid SD1.x LoRA safetensors file (header + zeroed fp16 tensors). */
export function sd15LoraFile(): Buffer {
  const tensors: Record<string, number[]> = {
    "lora_unet_down_blocks_0_attentions_0_transformer_blocks_0_attn2_to_k.lora_down.weight": [
      4, 768,
    ],
    "lora_unet_down_blocks_0_attentions_0_transformer_blocks_0_attn2_to_k.lora_up.weight": [320, 4],
  };
  const header: Record<string, unknown> = {};
  let offset = 0;
  for (const [name, shape] of Object.entries(tensors)) {
    const size = shape.reduce((a, b) => a * b, 2);
    header[name] = { dtype: "F16", shape, data_offsets: [offset, offset + size] };
    offset += size;
  }
  const json = Buffer.from(JSON.stringify(header));
  const length = Buffer.alloc(8);
  length.writeBigUInt64LE(BigInt(json.length));
  return Buffer.concat([length, json, Buffer.alloc(offset)]);
}
