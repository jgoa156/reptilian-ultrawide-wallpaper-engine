
// Tail rig + mouse follow (fragment). Replaces the "Rig: Tail" shake on every creature layer.
//
//  * Sway: an exact copy of WE's shake for the settings Rig: Tail used (no noise, friction 1 1,
//    bounds 0 1, direction centre, time-offset map on): offset = sin(speed * t + 2pi * timemap),
//    along the rig's flow map (g_Texture1, strength g_Amp).
//  * Follow: g_Follow (-1..1, set every frame by scripts/tail_follow.js; > 0 = art moves +x) pushes
//    the tail along its own field (g_Texture3, built by tools/tail_follow_field.py: a sideways bend
//    from y 1150 up to the tip, ~52 px at the tip, strain 0.25).
//  * Mix: sway * (1 - |follow|) + follow, so the combined strain stays <= max(0.284, 0.25).

#include "common.h"

varying vec4 v_TexCoord;

uniform sampler2D g_Texture0; // {"hidden":true}
uniform sampler2D g_Texture1; // {"label":"Sway flow map","mode":"flowmask","default":"util/noflow"}
uniform sampler2D g_Texture2; // {"label":"Time offset","mode":"opacitymask","default":"util/black"}
uniform sampler2D g_Texture3; // {"label":"Follow flow map","mode":"flowmask","default":"util/noflow"}
uniform float g_Time;

uniform float g_Speed; // {"material":"speed","label":"Sway speed","default":1.04,"range":[0,10]}
uniform float g_Amp; // {"material":"strength","label":"Sway strength","default":0.074,"range":[0.01,0.5]}
uniform float g_FollowAmp; // {"material":"followstrength","label":"Follow strength","default":0.108,"range":[0.01,0.5]}
uniform float g_Follow; // {"material":"follow","label":"Mouse follow (-1..1)","default":0,"range":[-1,1]}

void main() {
	float phase = texSample2D(g_Texture2, v_TexCoord.zw).r * M_PI_2;
	float sway = sin(g_Speed * g_Time + phase) * 0.996;
	float f = clamp(g_Follow, -1.0, 1.0);
	vec2 sflow = (texSample2D(g_Texture1, v_TexCoord.zw).rg - vec2(0.498, 0.498)) * 2.0;
	vec2 fflow = (texSample2D(g_Texture3, v_TexCoord.zw).rg - vec2(0.498, 0.498)) * 2.0;
	vec2 offset = sway * (1.0 - abs(f)) * g_Amp * g_Amp * sflow
		- f * g_FollowAmp * g_FollowAmp * fflow;                     // sample against the motion
	gl_FragColor = texSample2D(g_Texture0, v_TexCoord.xy + offset);
}
