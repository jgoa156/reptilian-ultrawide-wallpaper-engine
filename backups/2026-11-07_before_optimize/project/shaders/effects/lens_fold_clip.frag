
// Lens fold clip (fragment). Runs after the workshop "Lens distortion" on the Shadow layer.
// That lens is a strong barrel: uv' = c + (uv - c) * (1 - 0.5 * len2), with len2 = |(uv - c) / scale|^2.
// Past len2 = 2/3 the mapping folds back, so the far corners show squashed copies of whatever lies
// near the lens centre. For the white body and black ink that region is empty, but the shadow
// halo is not, and it appeared as a grey smear in the quad's top corner. This clips the folded
// zone; the real shadow lies entirely inside len2 < 0.55 (measured).

varying vec4 v_TexCoord;

uniform sampler2D g_Texture0; // {"hidden":true}
uniform vec2 g_Center; // {"material":"center","label":"Lens centre","default":"0.88288 0.55208"}
uniform vec2 g_Scale; // {"material":"scale","label":"Lens scale","default":"0.71171 1.66066"}
uniform vec2 g_Fold; // {"material":"fold","label":"Clip from..to (len2)","default":"0.55 0.62"}

void main() {
	vec4 c = texSample2D(g_Texture0, v_TexCoord.xy);
	vec2 d = (v_TexCoord.xy - g_Center) / g_Scale;
	float len2 = dot(d, d);
	c.a *= 1.0 - smoothstep(g_Fold.x, g_Fold.y, len2);
	gl_FragColor = c;
}
