// [COMBO] {"material":"ui_editor_properties_chromatic_aberration","combo":"CA","type":"options","default":1}
// [COMBO] {"material":"Anamorphic","combo":"ANAMORPHIC","type":"options","default":0}

uniform mat4 g_ModelViewProjectionMatrix;

uniform float u_zoom; // {"material":"zoom","label":"ui_editor_properties_zoom","default":1,"range":[0.5,1.5],"group":"Lens"}
uniform float u_general; // {"material":"general","label":"ui_editor_scene_options_general","default":1,"range":[0,1]}
uniform float u_distorsion1; // {"material":"Distorsion 1","default":0.5,"range":[-2,2],"group":"ui_editor_properties_distortion"}
uniform float u_distorsion2; // {"material":"Distorsion 2","default":0,"range":[-2,2],"group":"ui_editor_properties_distortion"}
uniform float u_aberration; // {"material":"chromaticAberration","label":"ui_editor_properties_chromatic_aberration","default":1,"range":[-2,2],"group":"ui_editor_properties_distortion"}
uniform vec2 u_center; // {"default":"0.5 0.5","group":"Lens","label":"ui_editor_properties_center","material":"center","position":true}
uniform float u_angle; // {"material":"angle","label":"ui_editor_properties_angle","default":0,"direction":true,"conversion":"rad2deg","group":"Lens"}
uniform float u_size; // {"material":"size","label":"ui_editor_properties_size","default":0.5,"range":[0,1],"group":"Lens"}

uniform vec4 g_Texture0Resolution;

attribute vec3 a_Position;
attribute vec2 a_TexCoord;

varying vec4 v_TexCoord; //xy = pixel coordinates, zw = aspect ratio
varying vec4 v_Distorsion; //xy = distortion, zw = chromatic aberrations
varying vec4 v_Transforms; //xy = center, zw = rotation

void main() {
	gl_Position = mul(vec4(a_Position, 1.0), g_ModelViewProjectionMatrix);
	v_TexCoord.xy = (a_TexCoord - CAST2(0.5)) * (1.0 + (1.0 - u_zoom) * u_general) + CAST2(0.5); //pixel coordinates
	v_TexCoord.zw = vec2(g_Texture0Resolution.y / g_Texture0Resolution.x, 1.0) * max(1e-6, u_size * 4.0); //aspect ratio
	v_Distorsion.xy = vec2(u_distorsion1, u_distorsion2 + u_distorsion2) * -u_general; //distortion
#if CA
	v_Distorsion.zw = u_aberration * 0.1 * v_Distorsion.xy; //chromatic aberrations
#else
	v_Distorsion.zw = 0;
#endif
	v_Transforms.xy = (1.0 - u_center - 0.5) * u_general - 0.5; //center
#if ANAMORPHIC
	v_Transforms.zw = vec2(cos(-u_angle), sin(-u_angle)); //rotation
#endif
}