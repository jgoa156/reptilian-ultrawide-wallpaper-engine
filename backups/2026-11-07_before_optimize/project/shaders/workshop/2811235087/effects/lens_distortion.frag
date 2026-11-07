// [COMBO] {"material":"ui_editor_properties_blend_mode","combo":"BLENDMODE","type":"imageblending","default":0}
// [COMBO] {"material":"Anamorphic","combo":"ANAMORPHIC","type":"options","default":0}
// [COMBO] {"material":"ui_editor_filemenu_show_grid","combo":"GRID","type":"options","default":0}

#include "common_blending.h"

uniform sampler2D g_Texture0; // {"material":"framebuffer","label":"ui_editor_properties_framebuffer","hidden":true}
uniform sampler2D g_Texture1; // {"combo":"MASK","label":"ui_editor_properties_opacity_mask","material":"mask","mode":"opacitymask","paintdefaultcolor":"1 1 1 1"}
uniform float u_alpha; // {"material":"ui_editor_properties_opacity","default":1,"range":[0,1]}
uniform float u_ratio; // {"material":"ratio","label":"ui_editor_properties_ratio","default":0.4184,"range":[0,5],"group":"Lens"}

varying vec4 v_TexCoord; //xy = pixel coordinates, zw = aspect ratio
varying vec4 v_Distorsion; //xy = distortion, zw = chromatic aberrations
varying vec4 v_Transforms; //xy = center, zw = rotation

void computeUV(in vec2 coord, in vec2 amount, in vec2 ca, in vec2 ratio, out vec2 uv, out vec2 uv1, out vec2 uv2){
    float len2 = dot(coord, coord);
    coord *= ratio;
    ca *= len2;
    amount *= len2;
    uv = coord * (1.0 + amount.x + amount.y * len2);
    uv1 = coord * (1.0 + amount.x + ca.x + (amount.y + ca.y) * len2);
    uv2 = coord * (1.0 + amount.x - ca.x + (amount.y - ca.y) * len2);
}

vec2 rotate(vec2 vec, vec2 rot){
	return vec2(vec.x * rot.x - vec.y * rot.y, vec.x * rot.y + vec.y * rot.x);
}

void main() {
    vec2 coord = (v_TexCoord.xy + v_Transforms.xy) / v_TexCoord.zw, uv, uv1, uv2;

#if ANAMORPHIC
    vec2 anamorphic = vec2(1.0, max(1e-6, u_ratio));
    coord = rotate(coord, vec2(v_Transforms.z, -v_Transforms.w)) / anamorphic;
    computeUV(coord, v_Distorsion.xy, v_Distorsion.zw, anamorphic, uv, uv1, uv2);
    uv = rotate(uv, v_Transforms.zw) * v_TexCoord.zw - v_Transforms.xy;
    uv1 = rotate(uv1, v_Transforms.zw) * v_TexCoord.zw - v_Transforms.xy;
    uv2 = rotate(uv2, v_Transforms.zw) * v_TexCoord.zw - v_Transforms.xy;
#else
    computeUV(coord, v_Distorsion.xy, v_Distorsion.zw, v_TexCoord.zw, uv, uv1, uv2);
    uv -= v_Transforms.xy, uv1 -= v_Transforms.xy, uv2 -= v_Transforms.xy;
#endif

    vec4 albedo = texSample2D(g_Texture0, uv);
    albedo.r = texSample2D(g_Texture0, uv1).r;
    albedo.b = texSample2D(g_Texture0, uv2).b;

#if GRID
    uv.x = (uv.x - 0.5) * v_TexCoord.w / v_TexCoord.z + 0.5;
    vec2 dist = abs(mod(uv - 0.5, CAST2(0.125)) - 0.0625);
    albedo.rgb = mix(albedo.rgb, round(1.0 - albedo.rgb), smoothstep(0.003, 0.0, min(dist.x, dist.y)));
#endif

#if MASK
    float mask = texSample2D(g_Texture1, v_TexCoord.xy).r;
#else
#define mask 1.0
#endif

    albedo.rgb = ApplyBlending(BLENDMODE, texSample2D(g_Texture0, v_TexCoord.xy).rgb, albedo.rgb, mask * u_alpha);
    gl_FragColor = albedo;
}