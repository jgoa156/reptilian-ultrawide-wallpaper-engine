// [COMBO] {"material":"ui_editor_properties_blend_mode","combo":"BLENDMODE","type":"imageblending","default":0}

#include "common.h"
#include "common_blending.h"

#define M_PI_F 3.14159265358979323846f

uniform float g_Time;

uniform sampler2D g_Texture0; // {"material":"framebuffer","label":"ui_editor_properties_framebuffer","hidden":true}
uniform float u_rOffset; // {"material":"Red Channel Offset","default":0.01,"range":[-0.1,0.1]}
uniform float u_gOffset; // {"material":"Green Channel Offset","default":-0.01,"range":[-0.1,0.1]}
uniform float u_bOffset; // {"material":"Blue Channel Offset","default":-0.02,"range":[-0.1,0.1]}
uniform float u_caOpacity; // {"default":"1","material":"Alpha"}
uniform sampler2D g_Texture1; // {"default":"util/noise","hidden":true,"material":"noise"}
uniform float u_shiftSpeed; // {"material":"speed","label":"Speed","default":0.005,"range":[-0.1,0.1]}
uniform float u_pointerSpeed; // {"material":"pointerspeed","label":"Cursor Influence","default":0,"range":[-0.02,0.02]}

varying vec4 v_TexCoord;
varying vec4 rValue;
varying vec4 gValue;
varying vec4 bValue;
varying vec4 timer;

uniform vec2 g_PointerPosition;
varying vec4 v_PointerUV;

#if AUDIOPROCESSING
varying float v_AudioShift;
#endif

void main() {
	vec4 scene = texSample2D(g_Texture0, v_TexCoord);
	vec4 timer = texSample2D(g_Texture0, v_TexCoord);
	float pointer = g_PointerPosition * u_pointerSpeed;

#if AUDIOPROCESSING
	vec4 rValue = texSample2D(g_Texture0, v_TexCoord.xy - (u_rOffset * v_AudioShift));
	vec4 gValue = texSample2D(g_Texture0, v_TexCoord.xy - (u_gOffset * v_AudioShift));
	vec4 bValue = texSample2D(g_Texture0, v_TexCoord.xy - (u_bOffset * v_AudioShift));
#else
	v_TexCoord += fmod(g_Time, M_PI_F / 10) * u_shiftSpeed;
	vec4 rValue = texSample2D(g_Texture0, v_TexCoord.xy - (u_rOffset * timer + pointer));
	vec4 gValue = texSample2D(g_Texture0, v_TexCoord.xy - (u_gOffset * timer + pointer));
	vec4 bValue = texSample2D(g_Texture0, v_TexCoord.xy - (u_bOffset * timer + pointer));
	
#endif	


vec3 finalColor = vec4(rValue.r, gValue.g, bValue.b, 0.1);
finalColor = ApplyBlending(BLENDMODE, scene.rgb, finalColor, u_caOpacity);

float alpha = scene.a;

	gl_FragColor = vec4(finalColor, alpha);
}

