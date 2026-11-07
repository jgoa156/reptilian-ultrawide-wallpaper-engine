
// Spectrum mandala (vertex): plain pass-through. The 13 piece levels come from the controller
// script as uniforms (arm0..arm12, bass). WE's GLSL->HLSL translator rejected reading the audio
// arrays into locals here and did not pass custom varyings to the fragment shader.

uniform mat4 g_ModelViewProjectionMatrix;

attribute vec3 a_Position;
attribute vec2 a_TexCoord;

varying vec4 v_TexCoord;

void main() {
	gl_Position = mul(vec4(a_Position, 1.0), g_ModelViewProjectionMatrix);
	v_TexCoord = a_TexCoord.xyxy;
}
