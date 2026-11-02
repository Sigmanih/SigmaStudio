export function detectLowEndGpu() {
  try {
    const probe = document.createElement('canvas');
    const gl = probe.getContext('webgl2') || probe.getContext('webgl');
    if (!gl) return true;
    const info = gl.getExtension('WEBGL_debug_renderer_info');
    const name = info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL) || '') : '';
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    return /v3d|videocore|llvmpipe|swiftshader|softpipe|mali-4|adreno \(tm\) 3/i.test(name);
  } catch {
    return true;
  }
}
