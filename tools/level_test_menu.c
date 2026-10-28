/* Development-only level launcher. Each level returns here on START. */
#include <3ds.h>
#include <citro2d.h>
#include "audio.h"

int dino_level1_main(void);
int dino_level2_main(void);
int dino_level3_main(void);
int dino_level4_main(void);
int dino_level5_main(void);
int dino_level6_main(void);
int dino_level7_main(void);
int dino_level8_main(void);
int dino_level9_main(void);

static C3D_RenderTarget *top;
static C3D_RenderTarget *bottom;
static C2D_TextBuf text_buf;

static void video_start(void) {
    gfxInitDefault();
    C3D_Init(C3D_DEFAULT_CMDBUF_SIZE);
    C2D_Init(C2D_DEFAULT_MAX_OBJECTS);
    C2D_Prepare();
    audio_init(); audio_menu(true);
    top = C2D_CreateScreenTarget(GFX_TOP, GFX_LEFT);
    bottom = C2D_CreateScreenTarget(GFX_BOTTOM, GFX_LEFT);
    text_buf = C2D_TextBufNew(256);
}

static void video_stop(void) {
    audio_shutdown();
    if (text_buf) C2D_TextBufDelete(text_buf);
    C2D_Fini();
    C3D_Fini();
    gfxExit();
}

int main(void) {
    int choice = 0;
    video_start();
    while (aptMainLoop()) {
        hidScanInput();
        u32 down = hidKeysDown();
        if (down & KEY_START) break;
        if (down & KEY_DUP) choice = (choice + 8) % 9;
        if (down & KEY_DDOWN) choice = (choice + 1) % 9;
        if (down & KEY_A) {
            video_stop();
            if (choice == 0) dino_level1_main();
            else if (choice == 1) dino_level2_main();
            else if (choice == 2) dino_level3_main();
            else if (choice == 3) dino_level4_main();
            else if (choice == 4) dino_level5_main();
            else if (choice == 5) dino_level6_main();
            else if (choice == 6) dino_level7_main();
            else if (choice == 7) dino_level8_main();
            else dino_level9_main();
            video_start();
            continue;
        }
        C3D_FrameBegin(C3D_FRAME_SYNCDRAW);
        C2D_TargetClear(top, C2D_Color32(23, 38, 30, 255));
        C2D_SceneBegin(top);
        if (text_buf) {
            C2D_TextBufClear(text_buf);
            C2D_Text title, item1, item2, item3, item4, item5, item6, item7, item8, item9, footer;
            C2D_TextParse(&title, text_buf, "DINO ATTACK - LEVEL TEST");
            C2D_TextParse(&item1, text_buf, choice == 0 ? "> Level 1" : "  Level 1");
            C2D_TextParse(&item2, text_buf, choice == 1 ? "> Level 2" : "  Level 2");
            C2D_TextParse(&item3, text_buf, choice == 2 ? "> Level 3 - T. rex" : "  Level 3 - T. rex");
            C2D_TextParse(&item4, text_buf, choice == 3 ? "> Level 4 - Predator" : "  Level 4 - Predator");
            C2D_TextParse(&item5, text_buf, choice == 4 ? "> Level 5 - Predator" : "  Level 5 - Predator");
            C2D_TextParse(&item6, text_buf, choice == 5 ? "> Level 6 - T. rex" : "  Level 6 - T. rex");
            C2D_TextParse(&item7, text_buf, choice == 6 ? "> Level 7 - Typhon" : "  Level 7 - Typhon");
            C2D_TextParse(&item8, text_buf, choice == 7 ? "> Level 8 - Typhon" : "  Level 8 - Typhon");
            C2D_TextParse(&item9, text_buf, choice == 8 ? "> Level 9 - Final boss" : "  Level 9 - Final boss");
            C2D_TextParse(&footer, text_buf, "D-Pad: select   A: play   START: exit");
            C2D_DrawText(&title, C2D_WithColor, 22, 24, 0, 0.65f, 0.65f, C2D_Color32(220, 245, 175, 255));
            C2D_DrawText(&item1, C2D_WithColor, 65, 47, 0, 0.43f, 0.50f, C2D_Color32(255, 255, 255, 255));
            C2D_DrawText(&item2, C2D_WithColor, 65, 65, 0, 0.43f, 0.50f, C2D_Color32(255, 255, 255, 255));
            C2D_DrawText(&item3, C2D_WithColor, 65, 83, 0, 0.43f, 0.50f, C2D_Color32(255, 255, 255, 255));
            C2D_DrawText(&item4, C2D_WithColor, 65, 101, 0, 0.43f, 0.50f, C2D_Color32(255, 255, 255, 255));
            C2D_DrawText(&item5, C2D_WithColor, 65, 119, 0, 0.43f, 0.50f, C2D_Color32(255, 255, 255, 255));
            C2D_DrawText(&item6, C2D_WithColor, 65, 137, 0, 0.43f, 0.50f, C2D_Color32(255, 255, 255, 255));
            C2D_DrawText(&item7, C2D_WithColor, 65, 155, 0, 0.43f, 0.50f, C2D_Color32(255, 255, 255, 255));
            C2D_DrawText(&item8, C2D_WithColor, 65, 173, 0, 0.43f, 0.46f, C2D_Color32(255, 255, 255, 255));
            C2D_DrawText(&item9, C2D_WithColor, 65, 191, 0, 0.43f, 0.43f, C2D_Color32(255, 255, 255, 255));
            C2D_DrawText(&footer, C2D_WithColor, 20, 213, 0, 0.34f, 0.34f, C2D_Color32(200, 220, 200, 255));
        }
        C2D_Flush();
        C2D_TargetClear(bottom, C2D_Color32(18, 25, 22, 255));
        C2D_SceneBegin(bottom);
        if (text_buf) {
            C2D_Text note;
            C2D_TextParse(&note, text_buf, "Test build: no game saves.\nSTART during a level returns here.");
            C2D_DrawText(&note, C2D_WithColor, 12, 25, 0, 0.45f, 0.45f, C2D_Color32(220, 225, 220, 255));
        }
        C2D_Flush();
        C3D_FrameEnd(0);
    }
    video_stop();
    return 0;
}
