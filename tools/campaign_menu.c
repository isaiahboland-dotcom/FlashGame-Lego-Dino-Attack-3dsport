/* Campaign launcher. Level state is saved only at level boundaries. */
#include <3ds.h>
#include <citro2d.h>
#include <stdio.h>
#include <string.h>
#include <stddef.h>
#include <sys/stat.h>
#include "campaign_art.h"
#include "audio.h"

int dino_level1_main(void); int dino_level2_main(void); int dino_level3_main(void);
int dino_level4_main(void); int dino_level5_main(void); int dino_level6_main(void);
int dino_level7_main(void); int dino_level8_main(void); int dino_level9_main(void);
static int (*const levels[])(void) = {dino_level1_main, dino_level2_main, dino_level3_main,
    dino_level4_main, dino_level5_main, dino_level6_main, dino_level7_main, dino_level8_main, dino_level9_main};
typedef struct { u32 magic, version, fingerprint, generation, current, unlocked, checksum; } Save;
static Save progress;
static int running_level;
static bool save_error;
static u32 checksum(const Save *s) {
    const u8 *p = (const u8 *)s; u32 h = 2166136261u;
    for (size_t i = 0; i < offsetof(Save, checksum); i++) h = (h ^ p[i]) * 16777619u;
    return h;
}
static bool read_slot(const char *path, Save *s) {
    FILE *f = fopen(path, "rb"); if (!f) return false;
    bool ok = fread(s, 1, sizeof(*s), f) == sizeof(*s) && fgetc(f) == EOF;
    fclose(f);
    return ok && s->magic == 0x44494e4f && s->version == 1 && s->fingerprint == CAMPAIGN_FINGERPRINT &&
        s->current >= 1 && s->current <= 9 && s->unlocked >= 1 && s->unlocked <= 9 &&
        s->current <= s->unlocked && s->checksum == checksum(s);
}
static bool load_progress(void) {
    Save a, b; bool aa = read_slot("sdmc:/3ds/dinodino/campaign-a.sav", &a);
    bool bb = read_slot("sdmc:/3ds/dinodino/campaign-b.sav", &b);
    if (!aa && !bb) { memset(&progress, 0, sizeof(progress)); progress.current = progress.unlocked = 1; return false; }
    progress = bb && (!aa || b.generation > a.generation) ? b : a; return true;
}
static bool write_progress(Save next) {
    next.magic = 0x44494e4f; next.version = 1; next.fingerprint = CAMPAIGN_FINGERPRINT;
    next.generation = progress.generation + 1; next.checksum = checksum(&next);
    mkdir("sdmc:/3ds", 0777); mkdir("sdmc:/3ds/dinodino", 0777);
    const char *path = next.generation & 1 ? "sdmc:/3ds/dinodino/campaign-a.sav" : "sdmc:/3ds/dinodino/campaign-b.sav";
    FILE *f = fopen(path, "wb"); if (!f) return false;
    bool ok = fwrite(&next, 1, sizeof(next), f) == sizeof(next);
    if (fclose(f) != 0) ok = false;
    if (ok) progress = next;
    return ok;
}
bool campaign_complete(void) {
    Save next = progress;
    if (running_level < 9) {
        next.current = running_level + 1;
        if (next.unlocked < next.current) next.unlocked = next.current;
    } else next.current = 9;
    return write_progress(next);
}
static C3D_RenderTarget *top, *bottom;
static C2D_TextBuf text_buf;
static C2D_SpriteSheet sheet;
static C2D_Image art;
static Tex3DS_SubTexture sub;
static void video_start(void) {
    gfxInitDefault(); C3D_Init(C3D_DEFAULT_CMDBUF_SIZE); C2D_Init(C2D_DEFAULT_MAX_OBJECTS); C2D_Prepare();
    audio_init(); audio_menu(true);
    top = C2D_CreateScreenTarget(GFX_TOP, GFX_LEFT); bottom = C2D_CreateScreenTarget(GFX_BOTTOM, GFX_LEFT);
    text_buf = C2D_TextBufNew(256);
    sheet = C2D_SpriteSheetLoadFromMem(CAMPAIGN_ART_DATA, CAMPAIGN_ART_SIZE);
    if (sheet) {
        sub.width = ART_W; sub.height = ART_H; sub.left = ART_X / 512.0f; sub.right = (ART_X + ART_W) / 512.0f;
        sub.top = 1.0f - ART_Y / 512.0f; sub.bottom = 1.0f - (ART_Y + ART_H) / 512.0f;
        art.tex = C2D_SpriteSheetGetImage(sheet, 0).tex; art.subtex = &sub;
    }
}
static void video_stop(void) {
    audio_shutdown();
    if (sheet) { C2D_SpriteSheetFree(sheet); sheet = NULL; }
    if (text_buf) C2D_TextBufDelete(text_buf);
    C2D_Fini(); C3D_Fini(); gfxExit();
}
int main(void) {
    bool available = load_progress(); int choice = 0, selected = 1, screen = 0, launch = 0;
    video_start();
    while (aptMainLoop()) {
        hidScanInput(); u32 down = hidKeysDown();
        if (down & KEY_START) { if (screen) screen = 0; else break; }
        if (!screen) {
            if (down & KEY_DUP) choice = (choice + 2) % 3;
            if (down & KEY_DDOWN) choice = (choice + 1) % 3;
            if (down & KEY_A) {
                if (choice == 0) launch = 1;
                else if (choice == 1 && available) launch = progress.current;
                else if (choice == 2) { screen = 1; selected = 1; }
            }
        } else {
            if (down & KEY_B) screen = 0;
            if (down & KEY_DUP) selected = selected > 1 ? selected - 1 : (int)progress.unlocked;
            if (down & KEY_DDOWN) selected = selected < (int)progress.unlocked ? selected + 1 : 1;
            if (down & KEY_A) launch = selected;
        }
        if (launch) {
            Save next = progress; next.current = launch;
            save_error = !write_progress(next);
            if (!save_error) {
                available = true; video_stop();
                while (launch) {
                    running_level = launch;
                    int completed = levels[launch - 1]();
                    launch = completed && running_level < 9 ? running_level + 1 : 0;
                }
                video_start();
            }
            launch = 0; continue;
        }
        C3D_FrameBegin(C3D_FRAME_SYNCDRAW); C2D_TargetClear(top, C2D_Color32(22, 35, 29, 255)); C2D_SceneBegin(top);
        if (sheet) {
            C2D_DrawImageAt(art, ART_OX * (400.0f/600), (240.0f-500.0f*(400.0f/600))/2 + ART_OY*(400.0f/600), 0, NULL,
                ART_FW*(400.0f/600)/ART_W, ART_FH*(400.0f/600)/ART_H);
            C2D_DrawRectSolid(38, 12, 0, 324, 198, C2D_Color32(0, 0, 0, 155));
            C2D_DrawRectSolid(0, 210, 0, 400, 30, C2D_Color32(0, 0, 0, 155));
        }
        if (text_buf) {
            C2D_TextBufClear(text_buf); C2D_Text title, body, footer; char label[256];
            C2D_TextParse(&title, text_buf, "DINO ATTACK");
            if (!screen) snprintf(label, sizeof(label), "%s Play\n%s Continue%s\n%s Level Select", choice == 0 ? ">" : " ", choice == 1 ? ">" : " ", available ? "" : " (no save)", choice == 2 ? ">" : " ");
            else snprintf(label, sizeof(label), "> Level %d\n\nUnlocked: %d of 9", selected, (int)progress.unlocked);
            C2D_TextParse(&body, text_buf, label);
            C2D_TextParse(&footer, text_buf, screen ? "D-Pad: select   A: play   B: back" : "D-Pad: select   A: confirm   START: exit");
            C2D_DrawText(&title, C2D_WithColor, 50, 28, 0, 0.85f, 0.85f, C2D_Color32(230,245,181,255));
            C2D_DrawText(&body, C2D_WithColor, 75, 92, 0, 0.65f, 0.65f, C2D_Color32(255,255,255,255));
            C2D_DrawText(&footer, C2D_WithColor, 20, 214, 0, 0.34f, 0.34f, C2D_Color32(200,220,200,255));
        }
        C2D_Flush(); C2D_TargetClear(bottom, C2D_Color32(17,25,22,255)); C2D_SceneBegin(bottom);
        if (text_buf && save_error) { C2D_Text warning; C2D_TextParse(&warning, text_buf, "Could not save to SD card."); C2D_DrawText(&warning, C2D_WithColor, 18, 25, 0, 0.45f, 0.45f, C2D_Color32(255,170,120,255)); }
        C2D_Flush(); C3D_FrameEnd(0);
    }
    video_stop(); return 0;
}
