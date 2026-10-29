/* Dino Attack 3DS port - pipeline test: t_rex wait animation + HUD panel. */
#include <3ds.h>
#include <citro2d.h>
#include <stdio.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include <sys/stat.h>
#include "gfx_meta.h"
typedef struct { float x, y, angle; int kind, hp; } EnemySpawn;
typedef struct { float x, y; int kind; bool active; } Pickup;
typedef struct { float x, y, angle; int kind, pickup; bool active; } Prop;
#include "level1.h"
#ifdef DINO_CAMPAIGN
extern bool campaign_complete(void);
#endif

#include "audio.h"

#define VIEW_W 600.0f
#define VIEW_H 500.0f

static C2D_SpriteSheet g_sheets[GFX_SHEETS];
static C2D_Image g_imgs[GFX_N];
static Tex3DS_SubTexture g_subs[GFX_N];

static int i_wait0 = -1, i_wait_n = 0, i_zone = -1;
static int i_health = -1, i_radar = -1, i_score = -1, i_hammer = -1, i_plasma = -1, i_acid = -1, i_choc = -1, i_intel = -1, i_fire = -1, i_menu_bg = -1;
#if !LEVEL_PREDATOR && !LEVEL_TYPHON
static int car_charge_frames[2][4];
static const float car_charge_ox[2][4] = {
    {CHOC_F001_ORIGIN_X, CHOC_F002_ORIGIN_X, CHOC_F003_ORIGIN_X, CHOC_F004_ORIGIN_X},
    {INTEL_F001_ORIGIN_X, INTEL_F002_ORIGIN_X, INTEL_F003_ORIGIN_X, INTEL_F004_ORIGIN_X}};
static const float car_charge_oy[2][4] = {
    {CHOC_F001_ORIGIN_Y, CHOC_F002_ORIGIN_Y, CHOC_F003_ORIGIN_Y, CHOC_F004_ORIGIN_Y},
    {INTEL_F001_ORIGIN_Y, INTEL_F002_ORIGIN_Y, INTEL_F003_ORIGIN_Y, INTEL_F004_ORIGIN_Y}};
#endif
#if LEVEL_BOSS_RED
static int i_superflame = -1, superflame_frames[6], superflame_count;
static const float superflame_ox[6] = {SUPERFLAME_F001_ORIGIN_X, SUPERFLAME_F002_ORIGIN_X, SUPERFLAME_F003_ORIGIN_X, SUPERFLAME_F004_ORIGIN_X, SUPERFLAME_F005_ORIGIN_X, SUPERFLAME_F006_ORIGIN_X};
static const float superflame_oy[6] = {SUPERFLAME_F001_ORIGIN_Y, SUPERFLAME_F002_ORIGIN_Y, SUPERFLAME_F003_ORIGIN_Y, SUPERFLAME_F004_ORIGIN_Y, SUPERFLAME_F005_ORIGIN_Y, SUPERFLAME_F006_ORIGIN_Y};
#endif
#if LEVEL_BOSS_YELLOW
static int i_eggball = -1;
#endif
#if LEVEL_RED_RAPTOR
static int i_flame = -1;
#endif
#if LEVEL_PREDATOR
static int i_turret = -1, i_nrg = -1, i_nrgintel = -1, i_dbz = -1;
#endif
static int i_pickup[3] = {-1, -1, -1};
static int i_prop[5] = {-1, -1, -1, -1, -1};
static const char *prop_names[5] = {"box_void", "box_hp", "box_weapon", "carcasse0", "carcasse1"};
static const float prop_origin_x[5] = {PROP_ORIGIN_0_X, PROP_ORIGIN_1_X, PROP_ORIGIN_2_X, PROP_ORIGIN_3_X, PROP_ORIGIN_4_X};
static const float prop_origin_y[5] = {PROP_ORIGIN_0_Y, PROP_ORIGIN_1_Y, PROP_ORIGIN_2_Y, PROP_ORIGIN_3_Y, PROP_ORIGIN_4_Y};
static Prop props[LEVEL_PROP_CAPACITY];
static const float pickup_origin_x[3] = {PICKUP_ORIGIN_0_X, PICKUP_ORIGIN_1_X, PICKUP_ORIGIN_2_X};
static const float pickup_origin_y[3] = {PICKUP_ORIGIN_0_Y, PICKUP_ORIGIN_1_Y, PICKUP_ORIGIN_2_Y};
static int i_tiles[LEVEL_MAX_TILE + 1];
static int i_foreground[LEVEL_MAX_FG + 1];
#define ENEMY_TYPES (7 + LEVEL_RED_RAPTOR + LEVEL_BOSS_YELLOW + 3 * LEVEL_TYPHON)
#define MAX_ENEMY_FRAMES 64
static int enemy_frames[ENEMY_TYPES][7][MAX_ENEMY_FRAMES];
static int enemy_frame_count[ENEMY_TYPES][7];
#if LEVEL_HAS_BOSS
static int boss_frames[5][12], boss_frame_count[5];
static const char *boss_states[5] = {"run", "prerugi", "rugi", "postrugi", "dead"};
#endif
#if LEVEL_RED_RAPTOR
#define RED_NAME , "raptor_rouge"
#define RED_OX , ENEMY_ORIGIN_7_X
#define RED_OY , ENEMY_ORIGIN_7_Y
#define RED_ZX , ENEMY_ZONE_7_X
#define RED_ZY , ENEMY_ZONE_7_Y
#define RED_RX , ENEMY_ZONE_7_RX
#define RED_RY , ENEMY_ZONE_7_RY
#define RED_SCORE , 50000
#elif LEVEL_BOSS_YELLOW
#define RED_NAME , "raptor_vert_sp"
#define RED_OX , ENEMY_ORIGIN_7_X
#define RED_OY , ENEMY_ORIGIN_7_Y
#define RED_ZX , ENEMY_ZONE_7_X
#define RED_ZY , ENEMY_ZONE_7_Y
#define RED_RX , ENEMY_ZONE_7_RX
#define RED_RY , ENEMY_ZONE_7_RY
#define RED_SCORE , 7500
#else
#define RED_NAME
#define RED_OX
#define RED_OY
#define RED_ZX
#define RED_ZY
#define RED_RX
#define RED_RY
#define RED_SCORE
#endif
#if LEVEL_TYPHON
#define FLY_NAMES , "ptero_vert", "ptero_jaune", "ptero_rouge"
#define FLY_OX , ENEMY_ORIGIN_8_X, ENEMY_ORIGIN_9_X, ENEMY_ORIGIN_10_X
#define FLY_OY , ENEMY_ORIGIN_8_Y, ENEMY_ORIGIN_9_Y, ENEMY_ORIGIN_10_Y
#define FLY_ZX , ENEMY_ZONE_8_X, ENEMY_ZONE_9_X, ENEMY_ZONE_10_X
#define FLY_ZY , ENEMY_ZONE_8_Y, ENEMY_ZONE_9_Y, ENEMY_ZONE_10_Y
#define FLY_RX , ENEMY_ZONE_8_RX, ENEMY_ZONE_9_RX, ENEMY_ZONE_10_RX
#define FLY_RY , ENEMY_ZONE_8_RY, ENEMY_ZONE_9_RY, ENEMY_ZONE_10_RY
#define FLY_SCORE , 20000, 40000, 50000
static int i_typhon_plasma = -1, i_typhon_intel = -1, i_typhon_dbz = -1, i_lazer = -1;
static int typhon_rotor[6], typhon_rotor_count;
#else
#define FLY_NAMES
#define FLY_OX
#define FLY_OY
#define FLY_ZX
#define FLY_ZY
#define FLY_RX
#define FLY_RY
#define FLY_SCORE
#endif
static const char *enemy_names[ENEMY_TYPES] = {"lezard_vert", "lezard_vert_sp", "lezard_jaune", "lezard_rouge", "raptor_vert", "lezard_jaune_sp", "raptor_jaune" RED_NAME FLY_NAMES};
static const float enemy_origin_x[ENEMY_TYPES] = {ENEMY_ORIGIN_0_X, ENEMY_ORIGIN_1_X, ENEMY_ORIGIN_2_X, ENEMY_ORIGIN_3_X, ENEMY_ORIGIN_4_X, ENEMY_ORIGIN_5_X, ENEMY_ORIGIN_6_X RED_OX FLY_OX};
static const float enemy_origin_y[ENEMY_TYPES] = {ENEMY_ORIGIN_0_Y, ENEMY_ORIGIN_1_Y, ENEMY_ORIGIN_2_Y, ENEMY_ORIGIN_3_Y, ENEMY_ORIGIN_4_Y, ENEMY_ORIGIN_5_Y, ENEMY_ORIGIN_6_Y RED_OY FLY_OY};
static const float enemy_zone_x[ENEMY_TYPES] = {ENEMY_ZONE_0_X, ENEMY_ZONE_1_X, ENEMY_ZONE_2_X, ENEMY_ZONE_3_X, ENEMY_ZONE_4_X, ENEMY_ZONE_5_X, ENEMY_ZONE_6_X RED_ZX FLY_ZX};
static const float enemy_zone_y[ENEMY_TYPES] = {ENEMY_ZONE_0_Y, ENEMY_ZONE_1_Y, ENEMY_ZONE_2_Y, ENEMY_ZONE_3_Y, ENEMY_ZONE_4_Y, ENEMY_ZONE_5_Y, ENEMY_ZONE_6_Y RED_ZY FLY_ZY};
static const float enemy_zone_rx[ENEMY_TYPES] = {ENEMY_ZONE_0_RX, ENEMY_ZONE_1_RX, ENEMY_ZONE_2_RX, ENEMY_ZONE_3_RX, ENEMY_ZONE_4_RX, ENEMY_ZONE_5_RX, ENEMY_ZONE_6_RX RED_RX FLY_RX};
static const float enemy_zone_ry[ENEMY_TYPES] = {ENEMY_ZONE_0_RY, ENEMY_ZONE_1_RY, ENEMY_ZONE_2_RY, ENEMY_ZONE_3_RY, ENEMY_ZONE_4_RY, ENEMY_ZONE_5_RY, ENEMY_ZONE_6_RY RED_RY FLY_RY};

static bool load_gfx(void) {
    i_wait_n = 0;
#if !LEVEL_PREDATOR && !LEVEL_TYPHON
    for (int k = 0; k < 2; k++) for (int f = 0; f < 4; f++) car_charge_frames[k][f] = -1;
#endif
#if LEVEL_BOSS_RED
    superflame_count = 0;
#endif
#if LEVEL_TYPHON
    typhon_rotor_count = 0;
#endif
    memset(enemy_frame_count, 0, sizeof(enemy_frame_count));
#if LEVEL_HAS_BOSS
    memset(boss_frame_count, 0, sizeof(boss_frame_count));
#endif
    for (int k = 0; k < ENEMY_TYPES; k++)
        for (int state = 0; state < 7; state++)
            for (int f = 0; f < MAX_ENEMY_FRAMES; f++) enemy_frames[k][state][f] = -1;
    for (int i = 0; i <= LEVEL_MAX_TILE; i++) i_tiles[i] = -1;
    for (int i = 0; i <= LEVEL_MAX_FG; i++) i_foreground[i] = -1;
    for (int i = 0; i < GFX_SHEETS; i++) {
        g_sheets[i] = C2D_SpriteSheetLoadFromMem(GFX_DATA[i], *GFX_DATA_SIZE[i]);
        if (!g_sheets[i]) {
            printf("sheet %d failed\n", i);
            return false;
        }
    }
    for (int i = 0; i < GFX_N; i++) {
        const Gfx *g = &GFX[i];
        g_subs[i].width = (u16)g->w;
        g_subs[i].height = (u16)g->h;
        g_subs[i].left = (float)g->x / 512.0f;
        g_subs[i].top = 1.0f - (float)g->y / 512.0f;
        g_subs[i].right = (float)(g->x + g->w) / 512.0f;
        g_subs[i].bottom = 1.0f - (float)(g->y + g->h) / 512.0f;
        g_imgs[i].tex = C2D_SpriteSheetGetImage(g_sheets[g->sheet], 0).tex;
        g_imgs[i].subtex = &g_subs[i];
        if (!strcmp(GFX_KEY[i], "dino/t_rex_vert/wait_f001")) i_wait0 = i;
        if (!strcmp(GFX_KEY[i], "dino/t_rex_vert/zone")) i_zone = i;
        if (!strcmp(GFX_KEY[i], "hud/main/health/f001")) i_health = i;
        if (!strcmp(GFX_KEY[i], "hud/main/radar/f001")) i_radar = i;
        if (!strcmp(GFX_KEY[i], "hud/main/score/f001")) i_score = i;
        if (!strcmp(GFX_KEY[i], "vehicle/hammer/pose")) i_hammer = i;
#if LEVEL_PREDATOR
        if (!strcmp(GFX_KEY[i], "vehicle/predator/turret")) i_turret = i;
        if (!strcmp(GFX_KEY[i], "projectile/nrg")) i_nrg = i;
        if (!strcmp(GFX_KEY[i], "projectile/nrgintel")) i_nrgintel = i;
        if (!strcmp(GFX_KEY[i], "projectile/dbz")) i_dbz = i;
#endif
        if (!strcmp(GFX_KEY[i], "projectile/plasma")) i_plasma = i;
        if (!strcmp(GFX_KEY[i], "projectile/acid")) i_acid = i;
        if (!strcmp(GFX_KEY[i], "projectile/choc")) i_choc = i;
        if (!strcmp(GFX_KEY[i], "projectile/intel")) i_intel = i;
#if !LEVEL_PREDATOR && !LEVEL_TYPHON
        int charge_frame;
        if (sscanf(GFX_KEY[i], "projectile/choc/f%d", &charge_frame) == 1 && charge_frame >= 1 && charge_frame <= 4)
            car_charge_frames[0][charge_frame - 1] = i;
        if (sscanf(GFX_KEY[i], "projectile/intel/f%d", &charge_frame) == 1 && charge_frame >= 1 && charge_frame <= 4)
            car_charge_frames[1][charge_frame - 1] = i;
#endif
        if (!strcmp(GFX_KEY[i], "projectile/fire")) i_fire = i;
#if LEVEL_TYPHON
        if (!strcmp(GFX_KEY[i], "projectile/plasmatyphon")) i_typhon_plasma = i;
        if (!strcmp(GFX_KEY[i], "projectile/nrginteltyphon")) i_typhon_intel = i;
        if (!strcmp(GFX_KEY[i], "projectile/dbztyphon")) i_typhon_dbz = i;
        if (!strcmp(GFX_KEY[i], "projectile/lazer")) i_lazer = i;
        int rotor_frame;
        if (sscanf(GFX_KEY[i], "vehicle/typhon/rotor/f%d", &rotor_frame) == 1 && rotor_frame >= 1 && rotor_frame <= 6) {
            typhon_rotor[rotor_frame - 1] = i;
            if (rotor_frame > typhon_rotor_count) typhon_rotor_count = rotor_frame;
        }
#endif
#if LEVEL_BOSS_RED
        if (!strcmp(GFX_KEY[i], "projectile/superflame")) i_superflame = i;
        int flame_frame;
        if (sscanf(GFX_KEY[i], "projectile/superflame/f%d", &flame_frame) == 1 && flame_frame >= 1 && flame_frame <= 6) {
            superflame_frames[flame_frame - 1] = i;
            if (flame_frame > superflame_count) superflame_count = flame_frame;
        }
#endif
#if LEVEL_BOSS_YELLOW
        if (!strcmp(GFX_KEY[i], "projectile/eggball")) i_eggball = i;
#endif
#if LEVEL_RED_RAPTOR
        if (!strcmp(GFX_KEY[i], "projectile/flame")) i_flame = i;
#endif
        if (!strcmp(GFX_KEY[i], "pickup/bonus_hp")) i_pickup[0] = i;
        if (!strcmp(GFX_KEY[i], "pickup/bonus_weapon")) i_pickup[1] = i;
        if (!strcmp(GFX_KEY[i], "pickup/bonus_egg")) i_pickup[2] = i;
        if (!strcmp(GFX_KEY[i], "menu/background")) i_menu_bg = i;
        for (int k = 0; k < 5; k++) {
            char key[64]; snprintf(key, sizeof(key), "prop/%s", prop_names[k]);
            if (!strcmp(GFX_KEY[i], key)) i_prop[k] = i;
        }
        const char *prefix = "tile/background/";
        if (!strncmp(GFX_KEY[i], prefix, strlen(prefix))) {
            int id = atoi(GFX_KEY[i] + strlen(prefix));
            if (id >= 0 && id <= LEVEL_MAX_TILE) i_tiles[id] = i;
        }
        char species[64], state_name[16]; int frame;
#if LEVEL_HAS_BOSS
        if (sscanf(GFX_KEY[i], "boss/%15[^/]/f%d", state_name, &frame) == 2)
            for (int s = 0; s < 5; s++)
                if (!strcmp(state_name, boss_states[s]) && frame >= 1 && frame <= 12) {
                    boss_frames[s][frame - 1] = i;
                    if (frame > boss_frame_count[s]) boss_frame_count[s] = frame;
                }
#endif
        if (sscanf(GFX_KEY[i], "enemy/%63[^/]/%15[^/]/f%d", species, state_name, &frame) == 3) {
            int state = !strcmp(state_name, "wait") ? 0 : !strcmp(state_name, "run") ? 1 :
                        !strcmp(state_name, "preshoot") ? 2 : !strcmp(state_name, "shoot") ? 3 :
                        !strcmp(state_name, "hurt") ? 4 : !strcmp(state_name, "dead") ? 5 :
                        !strcmp(state_name, "jump") ? 6 : -1;
            for (int k = 0; k < ENEMY_TYPES; k++)
                if (state >= 0 && !strcmp(species, enemy_names[k]) && frame >= 1 && frame <= MAX_ENEMY_FRAMES) {
                    enemy_frames[k][state][frame - 1] = i;
                    if (frame > enemy_frame_count[k][state]) enemy_frame_count[k][state] = frame;
                }
        }
        prefix = "tile/foreground/";
        if (!strncmp(GFX_KEY[i], prefix, strlen(prefix))) {
            int id = atoi(GFX_KEY[i] + strlen(prefix));
            if (id >= 0 && id <= LEVEL_MAX_FG) i_foreground[id] = i;
        }
    }
    if (i_wait0 >= 0)
        for (int i = i_wait0; i < GFX_N &&
             !strncmp(GFX_KEY[i], "dino/t_rex_vert/wait_f", 22); i++)
            i_wait_n++;
#if !LEVEL_HAS_BOSS || LEVEL_BOSS_YELLOW
    for (int k = 0; k < ENEMY_TYPES; k++)
        for (int state = 0; state < 7; state++) {
            if (!(LEVEL_ENEMY_TYPES_MASK & (1 << k))) continue;
            if (state == 6 && k != 4 && k != 6 && k != 7) continue;
            if (!enemy_frame_count[k][state]) return false;
            for (int f = 0; f < enemy_frame_count[k][state]; f++)
                if (enemy_frames[k][state][f] < 0) return false;
        }
#endif
    for (int k = 0; k < 3; k++) if (i_pickup[k] < 0) return false;
#if !LEVEL_PREDATOR && !LEVEL_TYPHON
    for (int k = 0; k < 2; k++) for (int f = 0; f < 4; f++) if (car_charge_frames[k][f] < 0) return false;
#endif
#if LEVEL_HAS_BOSS
    for (int s = 0; s < 5; s++) if (!boss_frame_count[s]) return false;
#endif
#if LEVEL_PREDATOR
    if (i_turret < 0 || i_nrg < 0 || i_nrgintel < 0 || i_dbz < 0) return false;
#endif
#if LEVEL_TYPHON
    if (i_typhon_plasma < 0 || i_typhon_intel < 0 || i_typhon_dbz < 0 || i_lazer < 0 || typhon_rotor_count != 6) return false;
#endif
#if LEVEL_BOSS_RED
    if (i_superflame < 0 || superflame_count != 6) return false;
#endif
#if LEVEL_BOSS_YELLOW
    if (i_eggball < 0) return false;
#endif
#if LEVEL_RED_RAPTOR
    if (i_flame < 0) return false;
#endif
    return i_wait0 >= 0 && i_wait_n > 0 && i_zone >= 0 && i_health >= 0 && i_radar >= 0 && i_score >= 0 && i_hammer >= 0 && i_plasma >= 0 && i_acid >= 0 && i_choc >= 0 && i_intel >= 0 && i_fire >= 0 && i_menu_bg >= 0;
}

static u16 background_tiles[LEVEL_ROWS * LEVEL_COLS];
static u8 background_collision[LEVEL_ROWS * LEVEL_COLS];
static u8 background_shot_collision[LEVEL_ROWS * LEVEL_COLS];
static u8 background_health[LEVEL_ROWS * LEVEL_COLS];
static u16 foreground_tiles[LEVEL_ROWS * LEVEL_COLS];
static u8 foreground_collision[LEVEL_ROWS * LEVEL_COLS];
static u8 foreground_shot_collision[LEVEL_ROWS * LEVEL_COLS];
static u8 scenery_health[LEVEL_ROWS * LEVEL_COLS];

static void reset_scenery(void) {
    memcpy(background_tiles, LEVEL_BACKGROUND, sizeof(background_tiles));
    memcpy(background_collision, LEVEL_COLLISION_B, sizeof(background_collision));
    memcpy(background_shot_collision, LEVEL_SHOT_B, sizeof(background_shot_collision));
    memcpy(background_health, LEVEL_B_HEALTH, sizeof(background_health));
    memcpy(foreground_tiles, LEVEL_FOREGROUND, sizeof(foreground_tiles));
    memcpy(foreground_collision, LEVEL_COLLISION_F, sizeof(foreground_collision));
    memcpy(foreground_shot_collision, LEVEL_SHOT_F, sizeof(foreground_shot_collision));
    for (int i = 0; i < LEVEL_ROWS * LEVEL_COLS; i++)
        scenery_health[i] = LEVEL_DESTRUCT_KIND[i] == 1 ? 12 : LEVEL_DESTRUCT_KIND[i] == 2 ? 4 : 0;
}

/* A versioned checkpoint is tied to the supplied game's data. */
#define SAVE_PATH_A "sdmc:/3ds/dinodino/level1-a.sav"
#define SAVE_PATH_B "sdmc:/3ds/dinodino/level1-b.sav"
typedef struct {
    u32 version, fingerprint, generation;
    float player_x, player_y, angle;
    int hp, eggs, weapon, bombs;
    u32 score;
    EnemySpawn enemies[LEVEL_ENEMY_COUNT];
    Pickup pickups[LEVEL_PICKUP_COUNT];
    u8 hidden[LEVEL_ENEMY_COUNT];
    u16 bg[LEVEL_ROWS * LEVEL_COLS], fg[LEVEL_ROWS * LEVEL_COLS];
    u8 bg_collision[LEVEL_ROWS * LEVEL_COLS], bg_shot[LEVEL_ROWS * LEVEL_COLS];
    u8 bg_health[LEVEL_ROWS * LEVEL_COLS];
    u8 fg_collision[LEVEL_ROWS * LEVEL_COLS], fg_shot[LEVEL_ROWS * LEVEL_COLS];
    u8 fg_health[LEVEL_ROWS * LEVEL_COLS];
    u32 checksum;
} GameSave;
static GameSave checkpoint, checkpoint_other;
static u32 checkpoint_generation;

static u32 checkpoint_checksum(const GameSave *save) {
    const u8 *data = (const u8 *)save;
    u32 hash = 2166136261u;
    for (size_t i = 0; i < offsetof(GameSave, checksum); i++) hash = (hash ^ data[i]) * 16777619u;
    return hash;
}

static bool checkpoint_read_file(const char *path, GameSave *candidate) {
    FILE *f = fopen(path, "rb");
    if (!f) return false;
    bool read_ok = fread(candidate, 1, sizeof(*candidate), f) == sizeof(*candidate) && fgetc(f) == EOF;
    fclose(f);
    if (!read_ok || candidate->version != 1 || candidate->fingerprint != SAVE_FINGERPRINT ||
        candidate->checksum != checkpoint_checksum(candidate) ||
        !isfinite(candidate->player_x) || !isfinite(candidate->player_y) || !isfinite(candidate->angle) ||
        candidate->player_x < 0 || candidate->player_x >= LEVEL_COLS * 100 ||
        candidate->player_y < 0 || candidate->player_y >= LEVEL_ROWS * 100 ||
        candidate->hp < 1 || candidate->hp > PLAYER_MAX_HP || candidate->eggs < 0 || candidate->eggs > LEVEL_EGG_TOTAL ||
        candidate->weapon < 0 || candidate->weapon > 2 || candidate->bombs < 0 || candidate->bombs > 255)
        return false;
    for (int i = 0; i < LEVEL_ENEMY_COUNT; i++) {
        EnemySpawn *e = &candidate->enemies[i];
        if (e->kind != LEVEL_ENEMIES[i].kind || e->hp > LEVEL_ENEMIES[i].hp ||
            !isfinite(e->x) || !isfinite(e->y) || !isfinite(e->angle) ||
            e->x < 0 || e->x >= LEVEL_COLS * 100 || e->y < 0 || e->y >= LEVEL_ROWS * 100 ||
            candidate->hidden[i] > 1) return false;
    }
    for (int i = 0; i < LEVEL_PICKUP_COUNT; i++) {
        Pickup *p = &candidate->pickups[i];
        if (p->kind != LEVEL_PICKUPS[i].kind || p->x != LEVEL_PICKUPS[i].x || p->y != LEVEL_PICKUPS[i].y)
            return false;
    }
    for (int i = 0; i < LEVEL_ROWS * LEVEL_COLS; i++)
        if (candidate->bg[i] > LEVEL_MAX_TILE || candidate->fg[i] > LEVEL_MAX_FG ||
            candidate->bg_collision[i] >= COLLISION_MASK_COUNT || candidate->bg_shot[i] >= COLLISION_MASK_COUNT ||
            candidate->fg_collision[i] >= COLLISION_MASK_COUNT || candidate->fg_shot[i] >= COLLISION_MASK_COUNT)
            return false;
    return true;
}

static bool checkpoint_read(void) {
#ifdef DINO_TEST_BUILD
    return false;
#endif
    bool a = checkpoint_read_file(SAVE_PATH_A, &checkpoint);
    bool b = checkpoint_read_file(SAVE_PATH_B, &checkpoint_other);
    if (!a && !b) { checkpoint_generation = 0; return false; }
    if (b && (!a || checkpoint_other.generation > checkpoint.generation)) checkpoint = checkpoint_other;
    checkpoint_generation = checkpoint.generation;
    return true;
}

static bool checkpoint_write(float x, float y, float angle, int hp, int eggs, int weapon, int bombs, u32 score,
                             const EnemySpawn *enemies, const Pickup *pickups, const bool *hidden) {
#ifdef DINO_TEST_BUILD
    return true;
#endif
    memset(&checkpoint, 0, sizeof(checkpoint));
    checkpoint.version = 1; checkpoint.fingerprint = SAVE_FINGERPRINT;
    checkpoint.generation = checkpoint_generation + 1;
    checkpoint.player_x = x; checkpoint.player_y = y; checkpoint.angle = angle;
    checkpoint.hp = hp; checkpoint.eggs = eggs; checkpoint.weapon = weapon; checkpoint.bombs = bombs;
    checkpoint.score = score;
    memcpy(checkpoint.enemies, enemies, sizeof(checkpoint.enemies));
    memcpy(checkpoint.pickups, pickups, sizeof(checkpoint.pickups));
    for (int i = 0; i < LEVEL_ENEMY_COUNT; i++) checkpoint.hidden[i] = hidden[i] ? 1 : 0;
    memcpy(checkpoint.bg, background_tiles, sizeof(checkpoint.bg));
    memcpy(checkpoint.fg, foreground_tiles, sizeof(checkpoint.fg));
    memcpy(checkpoint.bg_collision, background_collision, sizeof(checkpoint.bg_collision));
    memcpy(checkpoint.bg_shot, background_shot_collision, sizeof(checkpoint.bg_shot));
    memcpy(checkpoint.bg_health, background_health, sizeof(checkpoint.bg_health));
    memcpy(checkpoint.fg_collision, foreground_collision, sizeof(checkpoint.fg_collision));
    memcpy(checkpoint.fg_shot, foreground_shot_collision, sizeof(checkpoint.fg_shot));
    memcpy(checkpoint.fg_health, scenery_health, sizeof(checkpoint.fg_health));
    checkpoint.checksum = checkpoint_checksum(&checkpoint);
    mkdir("sdmc:/3ds", 0777);
    mkdir("sdmc:/3ds/dinodino", 0777);
    const char *path = checkpoint.generation & 1 ? SAVE_PATH_A : SAVE_PATH_B;
    FILE *f = fopen(path, "wb");
    if (!f) return false;
    bool wrote = fwrite(&checkpoint, 1, sizeof(checkpoint), f) == sizeof(checkpoint);
    if (fclose(f) != 0) wrote = false;
    if (!wrote) return false;
    checkpoint_generation = checkpoint.generation;
    return true;
}

static void checkpoint_restore_scenery(void) {
    memcpy(background_tiles, checkpoint.bg, sizeof(background_tiles));
    memcpy(foreground_tiles, checkpoint.fg, sizeof(foreground_tiles));
    memcpy(background_collision, checkpoint.bg_collision, sizeof(background_collision));
    memcpy(background_shot_collision, checkpoint.bg_shot, sizeof(background_shot_collision));
    memcpy(background_health, checkpoint.bg_health, sizeof(background_health));
    memcpy(foreground_collision, checkpoint.fg_collision, sizeof(foreground_collision));
    memcpy(foreground_shot_collision, checkpoint.fg_shot, sizeof(foreground_shot_collision));
    memcpy(scenery_health, checkpoint.fg_health, sizeof(scenery_health));
}

static void damage_scenery(float x, float y, int damage) {
    if (x < 0 || y < 0 || x >= LEVEL_COLS * 100 || y >= LEVEL_ROWS * 100) return;
    int px = (int)x, py = (int)y, cell = (py / 100) * LEVEL_COLS + px / 100;
    int bit = (py % 100) * 100 + px % 100;
    u8 flag = 1u << (bit % 8);
    if (scenery_health[cell] && (COLLISION_MASKS[foreground_shot_collision[cell]][bit / 8] & flag)) {
        if (damage < scenery_health[cell]) { scenery_health[cell] -= damage; return; }
        scenery_health[cell] = 0;
        audio_play(SND_EXPLO);
        if (LEVEL_DESTRUCT_KIND[cell] == 1) {
            foreground_tiles[cell] = 10;
            foreground_collision[cell] = RUBBLE_COLLISION;
            foreground_shot_collision[cell] = RUBBLE_SHOT_COLLISION;
        } else {
            foreground_tiles[cell] = 1;
            foreground_collision[cell] = EMPTY_COLLISION;
            foreground_shot_collision[cell] = EMPTY_SHOT_COLLISION;
        }
        return;
    }
    if (background_health[cell] && (COLLISION_MASKS[background_shot_collision[cell]][bit / 8] & flag)) {
        if (damage < background_health[cell]) { background_health[cell] -= damage; return; }
        background_health[cell] = 0;
        audio_play(SND_EXPLO);
        background_tiles[cell] = LEVEL_B_REPLACEMENT[cell];
        background_collision[cell] = LEVEL_B_REPLACEMENT_COLLISION[cell];
        background_shot_collision[cell] = LEVEL_B_REPLACEMENT_SHOT[cell];
    }
}

static int prop_at(float x, float y) {
    for (int i = 0; i < LEVEL_PROP_COUNT; i++) {
        const Prop *prop = &props[i];
        if (!prop->active) continue;
        float dx = x - prop->x, dy = y - prop->y;
        if (fabsf(dx) > 30 || fabsf(dy) > 30) continue;
        float a = prop->angle * (3.14159265f / 180.0f);
        float lx = dx * cosf(a) + dy * sinf(a);
        float ly = -dx * sinf(a) + dy * cosf(a);
        if (fabsf(lx) <= 20 && fabsf(ly) <= 20) return i;
    }
    return -1;
}

static void destroy_prop(int i, Pickup *pickups) {
    if (i < 0 || i >= LEVEL_PROP_COUNT || !props[i].active || props[i].kind >= 3) return;
    audio_play(SND_CAISSE);
    if (props[i].pickup >= 0 && props[i].pickup < LEVEL_PICKUP_COUNT)
        pickups[props[i].pickup].active = true;
    props[i].active = false;
}

/* Collision masks are sampled in world pixels; both decor layers matter. */
static bool scenery_solid(float x, float y, bool projectile) {
    if (x < 0 || y < 0 || x >= LEVEL_COLS * 100 || y >= LEVEL_ROWS * 100)
        return true;
    int px = (int)x, py = (int)y;
    int cell = (py / 100) * LEVEL_COLS + px / 100;
    int bit = (py % 100) * 100 + px % 100;
    unsigned char flag = 1u << (bit % 8);
    unsigned b = projectile ? background_shot_collision[cell] : background_collision[cell];
    unsigned f = projectile ? foreground_shot_collision[cell] : foreground_collision[cell];
    return (COLLISION_MASKS[b][bit / 8] & flag) ||
           (COLLISION_MASKS[f][bit / 8] & flag) || prop_at(x, y) >= 0;
}

/* Flying vehicles ignore the background and ground props, but foreground
   bounce zones such as tall buildings still block them. */
static bool vehicle_solid(float x, float y) {
#if LEVEL_TYPHON
    if (x < 0 || y < 0 || x >= LEVEL_COLS * 100 || y >= LEVEL_ROWS * 100)
        return true;
    int px = (int)x, py = (int)y;
    int cell = (py / 100) * LEVEL_COLS + px / 100;
    int bit = (py % 100) * 100 + px % 100;
    return (COLLISION_MASKS[foreground_collision[cell]][bit / 8] & (1u << (bit % 8))) != 0;
#else
    return scenery_solid(x, y, false);
#endif
}

static bool hammer_collides(float x, float y, float degrees) {
    float rad = degrees * (3.14159265f / 180.0f);
    float c = cosf(rad), s = sinf(rad);
    if (vehicle_solid(x, y)) return true;
    /* Sample the perimeter between original hit points as well as the points. */
    for (int edge = 0; edge < 4; edge++) {
        int next = (edge + 1) % 4;
        for (int step = 0; step < 8; step++) {
            float t = step / 8.0f;
            float dx = HAMMER_HITS[edge][0] * (1 - t) + HAMMER_HITS[next][0] * t;
            float dy = HAMMER_HITS[edge][1] * (1 - t) + HAMMER_HITS[next][1] * t;
            if (vehicle_solid(x + dx * c - dy * s, y + dx * s + dy * c)) return true;
        }
    }
    return false;
}

static bool try_hammer_turn(float *x, float *y, float current_angle, float next_angle) {
    if (!hammer_collides(*x, *y, next_angle)) return true;
    /* Small clearance adjustments allow a corner to pivot away from a wall. */
    for (int distance = 1; distance <= 4; distance++) {
        for (int direction = 0; direction < 8; direction++) {
            float a = direction * (3.14159265f / 4.0f);
            float nx = *x + distance * cosf(a), ny = *y + distance * sinf(a);
            bool clear_path = true;
            for (int step = 1; step <= distance; step++) {
                float px = *x + step * cosf(a), py = *y + step * sinf(a);
                if (hammer_collides(px, py, current_angle)) { clear_path = false; break; }
            }
            if (clear_path && !hammer_collides(nx, ny, next_angle)) {
                *x = nx; *y = ny;
                return true;
            }
        }
    }
    return false;
}

static bool enemy_hit(EnemySpawn *enemy, float x, float y) {
    if (enemy->hp <= 0) return false;
    int k = enemy->kind;
    float a = enemy->angle * (3.14159265f / 180.0f);
    float dx = x - enemy->x, dy = y - enemy->y;
    float local_x = dx * cosf(a) + dy * sinf(a) - enemy_zone_x[k];
    float local_y = -dx * sinf(a) + dy * cosf(a) - enemy_zone_y[k];
    float nx = local_x / enemy_zone_rx[k], ny = local_y / enemy_zone_ry[k];
    return nx * nx + ny * ny <= 1.0f;
}

static int enemy_score(int kind) {
    static const int scores[ENEMY_TYPES] = {1000, 3000, 2000, 5000, 15000, 4000, 30000 RED_SCORE FLY_SCORE};
    return scores[kind];
}

static bool lizard_blocked(float x, float y) {
    /* Small samples approximate the dinosaur's body until bounce physics is ported. */
    return scenery_solid(x, y, false) || scenery_solid(x - 12, y, false) ||
           scenery_solid(x + 12, y, false) || scenery_solid(x, y - 12, false) ||
           scenery_solid(x, y + 12, false);
}

static bool lizard_touches_hammer(EnemySpawn *enemy, float x, float y, float angle) {
    if (enemy_hit(enemy, x, y)) return true;
    float a = angle * (3.14159265f / 180.0f), c = cosf(a), s = sinf(a);
    for (int edge = 0; edge < 4; edge++) {
        int next = (edge + 1) % 4;
        for (int step = 0; step < 8; step++) {
            float t = step / 8.0f;
            float dx = HAMMER_HITS[edge][0] * (1 - t) + HAMMER_HITS[next][0] * t;
            float dy = HAMMER_HITS[edge][1] * (1 - t) + HAMMER_HITS[next][1] * t;
            if (enemy_hit(enemy, x + dx * c - dy * s, y + dx * s + dy * c)) return true;
        }
    }
    return false;
}

static bool point_hits_hammer(float x, float y, float player_x, float player_y, float angle) {
    float a = angle * (3.14159265f / 180.0f), c = cosf(a), s = sinf(a);
    float dx = x - player_x, dy = y - player_y;
    float lx = dx * c + dy * s, ly = -dx * s + dy * c;
    return lx >= -24 && lx <= 26 && ly >= -19 && ly <= 20;
}

#define MAX_ACID 16
typedef struct { bool active; float x, y, angle; int life, kind; } AcidShot;

#define MAX_PROJECTILES 24
typedef struct {
    bool active;
    float x, y, dx, dy, angle;
    int life, kind;
} Projectile;

int main(void) {
    gfxInitDefault();
    C3D_Init(C3D_DEFAULT_CMDBUF_SIZE);
    C2D_Init(C2D_DEFAULT_MAX_OBJECTS);
    C2D_Prepare();
    audio_init();


    bool ok = load_gfx();


    C3D_RenderTarget *top = C2D_CreateScreenTarget(GFX_TOP, GFX_LEFT);
    C3D_RenderTarget *bottom = C2D_CreateScreenTarget(GFX_BOTTOM, GFX_LEFT);

    float vscale = 400.0f / VIEW_W;
    if (VIEW_H * vscale > 240.0f) vscale = 240.0f / VIEW_H;

    const float half_view_w = 200.0f / vscale;
    bool show_zone = false;
    int map_mode = 0;
    float cam_x = LEVEL_SPAWN_X, cam_y = LEVEL_SPAWN_Y;
    float player_x = LEVEL_SPAWN_X, player_y = LEVEL_SPAWN_Y;
    float angle = LEVEL_SPAWN_ANGLE, turn_speed = 0, vx = 0, vy = 0;
    u64 previous_time = osGetTime();
    double accumulator = 0;
    Projectile shots[MAX_PROJECTILES] = {0};
    EnemySpawn enemies[LEVEL_ENEMY_COUNT];
    Pickup pickups[LEVEL_PICKUP_COUNT];
    memcpy(pickups, LEVEL_PICKUPS, sizeof(pickups));
    bool enemy_running[LEVEL_ENEMY_COUNT] = {0};
    bool enemy_hidden[LEVEL_ENEMY_COUNT] = {0};
    int enemy_timer[LEVEL_ENEMY_COUNT] = {0};
    int enemy_turn_timer[LEVEL_ENEMY_COUNT] = {0};
    int enemy_steer[LEVEL_ENEMY_COUNT] = {0};
    int enemy_hunt[LEVEL_ENEMY_COUNT] = {0};
    int enemy_windup[LEVEL_ENEMY_COUNT] = {0};
    int enemy_recovery[LEVEL_ENEMY_COUNT] = {0};
    int enemy_cooldown[LEVEL_ENEMY_COUNT] = {0};
    int enemy_hurt[LEVEL_ENEMY_COUNT] = {0};
    int enemy_dying[LEVEL_ENEMY_COUNT] = {0};
    int enemy_jump[LEVEL_ENEMY_COUNT] = {0}, enemy_jump_cooldown[LEVEL_ENEMY_COUNT] = {0};
    AcidShot acid_shots[MAX_ACID] = {0};
    memcpy(enemies, LEVEL_ENEMIES, sizeof(enemies));
    reset_scenery();
    memcpy(props, LEVEL_PROPS, sizeof(props));
    for (int e = 0; e < LEVEL_ENEMY_COUNT; e++) enemy_hidden[e] = enemies[e].kind == 1 || enemies[e].kind == 5;
    int fire_cooldown = 0, gun_side = 1, player_hp = PLAYER_MAX_HP, hurt_timer = 0;
    int burst_left = 0, burst_kind = 0, burst_delay = 0, charge_ticks = 0;
    bool fire_previous = false, fire_press_pending = false, fire_release_pending = false;
    int eggs = 0, weapon_level = 0, bombs = 1;
    unsigned int score_value = 0;
    bool level_won = false, bomb_requested = false;
#ifdef DINO_CAMPAIGN
    bool completion_recorded = false, campaign_advance = false;
#endif
#if LEVEL_HAS_BOSS
    float boss_x = BOSS_X, boss_y = BOSS_Y, boss_angle = BOSS_ANGLE;
    int boss_hp = BOSS_MAX_HP, boss_phase = 0, boss_tick = 0;
#endif
    int bomb_flash = 0;
    int menu_screen = 0, menu_choice = 0; /* 0 main, 1 level select, 2 game */
    bool start_requested = false, resume_available = checkpoint_read(), save_error = false;
#ifdef DINO_TEST_BUILD
    menu_screen = 2; map_mode = 3; start_requested = true;
#endif
    u64 last_save_ms = osGetTime();
    C2D_TextBuf menu_buf = C2D_TextBufNew(256);
    C2D_TextBuf text_buf = C2D_TextBufNew(80);
    C2D_Text disabled_text, won_text;
    C2D_TextBuf hud_buf = C2D_TextBufNew(128);
    if (text_buf) {
        C2D_TextParse(&disabled_text, text_buf, "Vehicle disabled - SELECT to restart");
        C2D_TextOptimize(&disabled_text);
#ifdef DINO_CAMPAIGN
#if LEVEL_BOSS_RED
        C2D_TextParse(&won_text, text_buf, "Game complete! A: main menu");
#else
        C2D_TextParse(&won_text, text_buf, "Level complete! A: continue");
#endif
#else
        C2D_TextParse(&won_text, text_buf, "Level complete! SELECT to restart");
#endif
        C2D_TextOptimize(&won_text);
    }
    bool system_exit = false;
    while (true) {
        if (!aptMainLoop()) { system_exit = true; break; }
        hidScanInput();
        u32 kDown = hidKeysDown(), held = hidKeysHeld();
        audio_menu(menu_screen != 2 || level_won);
        audio_engine(LEVEL_TYPHON ? 2 : LEVEL_PREDATOR ? 1 : 0,
                     (held & (KEY_A | KEY_B | KEY_DUP | KEY_DDOWN)) != 0,
                     menu_screen == 2 && player_hp > 0 && !level_won);
#ifdef DINO_CAMPAIGN
        if (level_won && !completion_recorded) completion_recorded = campaign_complete();
        if (level_won && completion_recorded && (kDown & KEY_A)) { campaign_advance = true; break; }
#endif
#ifdef DINO_TEST_BUILD
        if (kDown & KEY_START) break;
#endif
        if (menu_screen != 2) {
            if (kDown & KEY_START) break;
            if (menu_screen == 0) {
                if (kDown & KEY_DUP) menu_choice = (menu_choice + 2) % 3;
                if (kDown & KEY_DDOWN) menu_choice = (menu_choice + 1) % 3;
                if (kDown & KEY_A) {
                    if (menu_choice == 0) { start_requested = true; menu_screen = 2; map_mode = 3; }
                    else if (menu_choice == 1 && checkpoint_read()) {
                        memcpy(enemies, checkpoint.enemies, sizeof(enemies));
                        memcpy(pickups, checkpoint.pickups, sizeof(pickups));
                        for (int e = 0; e < LEVEL_ENEMY_COUNT; e++) enemy_hidden[e] = checkpoint.hidden[e] != 0;
                        checkpoint_restore_scenery();
                        player_x = checkpoint.player_x; player_y = checkpoint.player_y; angle = checkpoint.angle;
                        cam_x = fminf(fmaxf(player_x, half_view_w), LEVEL_COLS * 100 - half_view_w);
                        cam_y = fminf(fmaxf(player_y, 250), LEVEL_ROWS * 100 - 250);
                        player_hp = checkpoint.hp; eggs = checkpoint.eggs; weapon_level = checkpoint.weapon;
                        bombs = checkpoint.bombs; score_value = checkpoint.score;
                        vx = vy = turn_speed = 0; hurt_timer = fire_cooldown = 0;
                        level_won = bomb_requested = false; bomb_flash = 0;
                        memset(enemy_running, 0, sizeof(enemy_running));
                        memset(enemy_timer, 0, sizeof(enemy_timer));
                        memset(enemy_turn_timer, 0, sizeof(enemy_turn_timer));
                        memset(enemy_steer, 0, sizeof(enemy_steer));
                        memset(enemy_hunt, 0, sizeof(enemy_hunt));
                        memset(enemy_windup, 0, sizeof(enemy_windup));
                        memset(enemy_recovery, 0, sizeof(enemy_recovery));
                        memset(enemy_cooldown, 0, sizeof(enemy_cooldown));
                        memset(enemy_hurt, 0, sizeof(enemy_hurt));
                        memset(enemy_dying, 0, sizeof(enemy_dying));
                        memset(enemy_jump, 0, sizeof(enemy_jump));
                        memset(enemy_jump_cooldown, 0, sizeof(enemy_jump_cooldown));
                        memset(shots, 0, sizeof(shots)); memset(acid_shots, 0, sizeof(acid_shots));
                        burst_left = burst_kind = burst_delay = charge_ticks = 0;
                        fire_previous = fire_press_pending = fire_release_pending = false;
                        menu_screen = 2; map_mode = 3; last_save_ms = osGetTime();
                    } else if (menu_choice == 2) menu_screen = 1;
                }
            } else {
                if (kDown & KEY_B) menu_screen = 0;
                if (kDown & KEY_A) { start_requested = true; menu_screen = 2; map_mode = 3; }
            }
            if (menu_screen != 2) {
                C3D_FrameBegin(C3D_FRAME_SYNCDRAW);
                C2D_TargetClear(top, C2D_Color32(22, 35, 29, 255));
                C2D_SceneBegin(top);
                if (ok && i_menu_bg >= 0) {
                    const Gfx *bg = &GFX[i_menu_bg];
                    /* Center-crop the original 600x500 art to the wide top screen. */
                    float scale = 400.0f / 600.0f;
                    C2D_DrawImageAt(g_imgs[i_menu_bg], bg->ox * scale,
                                    (240.0f - 500.0f * scale) / 2.0f + bg->oy * scale,
                                    0, NULL, bg->fw * scale / bg->w, bg->fh * scale / bg->h);
                    C2D_DrawRectSolid(38, 12, 0, 324, 198, C2D_Color32(0, 0, 0, 155));
                    C2D_DrawRectSolid(0, 210, 0, 400, 30, C2D_Color32(0, 0, 0, 155));
                }
                if (menu_buf) {
                    C2D_TextBufClear(menu_buf);
                    C2D_Text title, body, footer;
                    C2D_TextParse(&title, menu_buf, "DINO ATTACK");
                    char choices[256];
                    if (menu_screen == 0)
                        snprintf(choices, sizeof(choices), "%s Start\n%s Resume%s\n%s Level Select",
                                 menu_choice == 0 ? ">" : " ", menu_choice == 1 ? ">" : " ",
                                 resume_available ? "" : " (no save)", menu_choice == 2 ? ">" : " ");
                    else snprintf(choices, sizeof(choices), "> Level 1\n\nLevels 2-9: not available yet");
                    C2D_TextParse(&body, menu_buf, choices);
                    C2D_TextParse(&footer, menu_buf, menu_screen == 0 ?
                                  "D-Pad: select   A: confirm   START: exit" : "A: start   B: back");
                    C2D_DrawText(&title, C2D_WithColor, 50, 28, 0, 0.85f, 0.85f, C2D_Color32(230, 245, 181, 255));
                    C2D_DrawText(&body, C2D_WithColor, 75, 92, 0, 0.65f, 0.65f, C2D_Color32(255, 255, 255, 255));
                    C2D_DrawText(&footer, C2D_WithColor, 20, 214, 0, 0.34f, 0.34f, C2D_Color32(200, 220, 200, 255));
                }
                C2D_Flush();
                C2D_TargetClear(bottom, C2D_Color32(17, 25, 22, 255));
                C2D_SceneBegin(bottom);
                if (menu_buf && save_error) {
                    C2D_Text warning;
                    C2D_TextParse(&warning, menu_buf, "Could not save to SD card.");
                    C2D_DrawText(&warning, C2D_WithColor, 18, 25, 0, 0.45f, 0.45f, C2D_Color32(255, 170, 120, 255));
                }
                C2D_Flush(); C3D_FrameEnd(0);
                previous_time = osGetTime(); accumulator = 0;
                continue;
            }
            previous_time = osGetTime(); accumulator = 0;
        } else if (kDown & KEY_START) {
            if (player_hp > 0 && !level_won) {
                save_error = !checkpoint_write(player_x, player_y, angle, player_hp, eggs, weapon_level, bombs,
                                               score_value, enemies, pickups, enemy_hidden);
                resume_available = checkpoint_read();
            }
            menu_screen = 0; menu_choice = 0; previous_time = osGetTime(); accumulator = 0;
            continue;
        }
        if (start_requested || ((kDown & KEY_SELECT) && map_mode == 3)) {
            memcpy(enemies, LEVEL_ENEMIES, sizeof(enemies));
            reset_scenery();
            memcpy(props, LEVEL_PROPS, sizeof(props));
            memcpy(pickups, LEVEL_PICKUPS, sizeof(pickups));
            eggs = weapon_level = score_value = 0; bombs = 1; level_won = false; bomb_requested = false;
#ifdef DINO_CAMPAIGN
            completion_recorded = false;
#endif
#if LEVEL_HAS_BOSS
            boss_x = BOSS_X; boss_y = BOSS_Y; boss_angle = BOSS_ANGLE;
            boss_hp = BOSS_MAX_HP; boss_phase = boss_tick = 0;
#endif
            memset(enemy_running, 0, sizeof(enemy_running));
            for (int e = 0; e < LEVEL_ENEMY_COUNT; e++) enemy_hidden[e] = enemies[e].kind == 1 || enemies[e].kind == 5;
            memset(enemy_timer, 0, sizeof(enemy_timer));
            memset(enemy_turn_timer, 0, sizeof(enemy_turn_timer));
            memset(enemy_steer, 0, sizeof(enemy_steer));
            memset(enemy_hunt, 0, sizeof(enemy_hunt));
            memset(enemy_windup, 0, sizeof(enemy_windup));
            memset(enemy_recovery, 0, sizeof(enemy_recovery));
            memset(enemy_cooldown, 0, sizeof(enemy_cooldown));
            memset(enemy_hurt, 0, sizeof(enemy_hurt));
            memset(enemy_dying, 0, sizeof(enemy_dying));
            memset(enemy_jump, 0, sizeof(enemy_jump));
            memset(enemy_jump_cooldown, 0, sizeof(enemy_jump_cooldown));
            memset(acid_shots, 0, sizeof(acid_shots));
            memset(shots, 0, sizeof(shots));
            player_x = LEVEL_SPAWN_X; player_y = LEVEL_SPAWN_Y;
            angle = LEVEL_SPAWN_ANGLE; turn_speed = vx = vy = 0;
            player_hp = PLAYER_MAX_HP; hurt_timer = fire_cooldown = 0;
            start_requested = false; bomb_flash = 0;
            save_error = !checkpoint_write(player_x, player_y, angle, player_hp, eggs, weapon_level, bombs,
                                           score_value, enemies, pickups, enemy_hidden);
            resume_available = checkpoint_read(); last_save_ms = osGetTime();
            burst_left = burst_kind = burst_delay = charge_ticks = 0;
            fire_previous = fire_press_pending = fire_release_pending = false;
        }
        if (kDown & KEY_X) {
            if (map_mode == 3) bomb_requested = true;
            else show_zone = !show_zone;
        }
#ifndef DINO_CAMPAIGN
        if (kDown & KEY_Y) map_mode = (map_mode + 1) % 4;
#endif
        bool fire_down = map_mode == 3 && (held & (KEY_L | KEY_R));
        if (fire_down && !fire_previous) fire_press_pending = true;
        if (!fire_down && fire_previous) fire_release_pending = true;
        fire_previous = fire_down;
        circlePosition circle;
        hidCircleRead(&circle);
        if (map_mode == 1 || map_mode == 2) {
            if (held & KEY_LEFT) cam_x -= 5.0f;
            if (held & KEY_RIGHT) cam_x += 5.0f;
            if (held & KEY_UP) cam_y -= 5.0f;
            if (held & KEY_DOWN) cam_y += 5.0f;
            if (cam_x < half_view_w) cam_x = half_view_w;
            if (cam_y < 250) cam_y = 250;
            if (cam_x > LEVEL_COLS * 100 - half_view_w) cam_x = LEVEL_COLS * 100 - half_view_w;
            if (cam_y > LEVEL_ROWS * 100 - 250) cam_y = LEVEL_ROWS * 100 - 250;
        }
        u64 now = osGetTime();
        double elapsed = (now - previous_time) / 1000.0;
        previous_time = now;
        if (elapsed > 0.1) elapsed = 0.1;
        if (map_mode == 3) {
            accumulator += elapsed;
            while (accumulator >= 1.0 / 24.0) {
                if (level_won) { accumulator = 0; break; }
                int old_hp = player_hp;
#if LEVEL_HAS_BOSS
                int old_boss_phase = boss_phase;
#endif
                float thrust = (held & (KEY_DUP | KEY_A)) ? 1.0f :
                               (held & (KEY_DDOWN | KEY_B)) ? -0.6f : 0;
                float steer = (held & KEY_DLEFT) ? -1.0f : (held & KEY_DRIGHT) ? 1.0f : 0;
                bool stick_active = (circle.dx * circle.dx + circle.dy * circle.dy) > 30 * 30;
                if (!(held & (KEY_DLEFT | KEY_DRIGHT)) && stick_active) {
                    float target = atan2f(-circle.dy, circle.dx) * (180.0f / 3.14159265f);
                    float error = remainderf(target - angle, 360.0f);
                    if (fabsf(error) < 1.0f && fabsf(turn_speed) < 1.0f) {
                        angle += error;
                        turn_speed = 0;
                        steer = 0;
                    } else {
                        /* Brake the turn as the chassis approaches the requested heading. */
                        steer = fminf(1.0f, fmaxf(-1.0f,
                                    (error * 0.45f - turn_speed * 0.7f) / 3.1f));
                    }
                } else if (thrust < 0) steer *= 1.3f;
                if (player_hp <= 0) { thrust = steer = turn_speed = vx = vy = 0; }
                turn_speed = turn_speed * (LEVEL_PREDATOR ? 0.6f : 0.7f) + steer * (LEVEL_PREDATOR ? 2.5f : 3.1f);
                float turn_limit = LEVEL_PREDATOR ? 7.0f : 15.0f;
                if (turn_speed > turn_limit) turn_speed = turn_limit;
                if (turn_speed < -turn_limit) turn_speed = -turn_limit;
                float rad = angle * (3.14159265f / 180.0f);
                float dx = cosf(rad), dy = sinf(rad);
                float forward = vx * dx + vy * dy;
                float side = -vx * dy + vy * dx;
                forward = forward * (LEVEL_PREDATOR ? 0.8f : 0.875f) + thrust * (LEVEL_PREDATOR ? 4.0f : 3.0f);
                side *= LEVEL_PREDATOR ? 0.65f : 0.75f;
                float speed = hypotf(forward, side);
                float max_speed = LEVEL_TYPHON ? 25.0f : 22.0f;
                if (speed > max_speed) { forward *= max_speed / speed; side *= max_speed / speed; }
                vx = forward * dx - side * dy;
                vy = forward * dy + side * dx;
                float next_angle = angle + turn_speed;
                if (try_hammer_turn(&player_x, &player_y, angle, next_angle)) angle = next_angle;
                else turn_speed = 0;
                /* Small steps avoid tunneling through thin masks at high speed. */
                int steps = (int)ceilf(fmaxf(fabsf(vx), fabsf(vy)) / 2.0f);
                if (steps < 1) steps = 1;
                float step_x = vx / steps, step_y = vy / steps;
                for (int step = 0; step < steps; step++) {
                    if (!hammer_collides(player_x + step_x, player_y + step_y, angle)) {
                        player_x += step_x; player_y += step_y;
                    } else {
                        if (!hammer_collides(player_x + step_x, player_y, angle)) player_x += step_x;
                        else { vx = 0; step_x = 0; }
                        if (!hammer_collides(player_x, player_y + step_y, angle)) player_y += step_y;
                        else { vy = 0; step_y = 0; }
                    }
                }
                if (player_x < 0) { player_x = 0; vx = 0; }
                if (player_y < 0) { player_y = 0; vy = 0; }
                if (player_x > LEVEL_COLS * 100) { player_x = LEVEL_COLS * 100; vx = 0; }
                if (player_y > LEVEL_ROWS * 100) { player_y = LEVEL_ROWS * 100; vy = 0; }
                if (player_hp > 0) {
                    for (int p = 0; p < LEVEL_PICKUP_COUNT; p++) {
                        Pickup *pickup = &pickups[p];
                        if (!pickup->active) continue;
                        float dx = pickup->x - player_x, dy = pickup->y - player_y;
                        if (dx * dx + dy * dy > 35.0f * 35.0f) continue;
                        if (pickup->kind == 0) {
                            if (player_hp >= PLAYER_MAX_HP) continue;
                            player_hp = PLAYER_MAX_HP;
                        } else if (pickup->kind == 1) {
                            if (weapon_level < 2) weapon_level++; else bombs++;
                        } else {
                            eggs++;
                            if (eggs == LEVEL_EGG_TOTAL) score_value += 500000;
                        }
                        audio_play(pickup->kind == 2 ? (eggs == LEVEL_EGG_TOTAL ? SND_BONUS_EGG_ALL : SND_BONUS_EGG) : SND_BONUS);
                        pickup->active = false;
                    }
                    int tile_x = (int)(player_x / 100), tile_y = (int)(player_y / 100);
                    if (tile_x >= 0 && tile_x < LEVEL_COLS && tile_y >= 0 && tile_y < LEVEL_ROWS) {
                        unsigned tile = foreground_tiles[tile_y * LEVEL_COLS + tile_x];
                        for (int f = 0; f < LEVEL_FINISH_COUNT; f++) {
                            if (tile == LEVEL_FINISH_IDS[f]) {
                                int killed = 0;
                                for (int e = 0; e < LEVEL_ENEMY_COUNT; e++) if (enemies[e].hp <= 0) killed++;
                                if (LEVEL_ENEMY_COUNT > 0) score_value += (killed * 100 / (LEVEL_ENEMY_COUNT ? LEVEL_ENEMY_COUNT : 1)) * 5000;
                                if (LEVEL_EGG_TOTAL > 0) score_value += (eggs * 100 / LEVEL_EGG_TOTAL) * 5000;
                                level_won = true; vx = vy = 0;
                                break;
                            }
                        }
                    }
                }
                if (level_won) { accumulator = 0; break; }
                if (bomb_requested) {
                    bomb_requested = false;
                    if (bombs > 0 && player_hp > 0) {
                        bombs--;
                        audio_play(SND_TIRSPECIAL);
                        bomb_flash = 32;
#if LEVEL_HAS_BOSS
                        if (boss_hp > 0 && fabsf(boss_x - cam_x) <= half_view_w && fabsf(boss_y - cam_y) <= 250) {
                            boss_hp -= BOSS_BOMB_DAMAGE;
                            if (boss_hp <= 0) { boss_hp = 0; boss_phase = 4; boss_tick = 0; score_value += BOSS_SCORE; }
                        }
#endif
                        for (int p = 0; p < LEVEL_PROP_COUNT; p++)
                            if (props[p].active && fabsf(props[p].x - cam_x) <= half_view_w &&
                                fabsf(props[p].y - cam_y) <= 250) destroy_prop(p, pickups);
                        for (int e = 0; e < LEVEL_ENEMY_COUNT; e++) {
                            EnemySpawn *enemy = &enemies[e];
                            if (enemy->hp <= 0 || fabsf(enemy->x - cam_x) > half_view_w ||
                                fabsf(enemy->y - cam_y) > 250) continue;
                            enemy_hidden[e] = false;
                            enemy->hp = 0;
                            enemy_dying[e] = enemy_frame_count[enemy->kind][5];
                            score_value += enemy_score(enemy->kind);
                        }
                    }
                }
                if (bomb_flash > 0) bomb_flash--;
                if (hurt_timer > 0) hurt_timer--;
#if LEVEL_HAS_BOSS
                if (boss_phase == 4) {
                    if (++boss_tick >= 90) { level_won = true; vx = vy = 0; }
                } else if (boss_phase == 0) {
                    float target = atan2f(player_y - boss_y, player_x - boss_x) * (180.0f / 3.14159265f);
                    float error = remainderf(target - boss_angle, 360.0f);
                    boss_angle += fminf(5.0f, fmaxf(-5.0f, error));
                    float rad = boss_angle * (3.14159265f / 180.0f);
                    if (hypotf(player_x - boss_x, player_y - boss_y) > 120.0f) {
                        float nx = boss_x + cosf(rad) * 5.0f, ny = boss_y + sinf(rad) * 5.0f;
                        if (!lizard_blocked(nx, ny)) { boss_x = nx; boss_y = ny; }
                    }
                    if (++boss_tick >= 100) { boss_phase = 1; boss_tick = 0; }
                } else {
                    int duration = boss_phase == 2 ? 82 : 12;
#if LEVEL_BOSS_RED
                    if (boss_phase == 2 && boss_tick % 3 == 0) {
                        float phase = 4.0f * (boss_tick % 41) / 41.0f;
                        float sweep = 90.0f * (phase > 2.0f ? 3.0f - phase : phase - 1.0f);
                        float a = boss_angle * (3.14159265f / 180.0f);
                        for (int i = 0; i < MAX_ACID; i++) if (!acid_shots[i].active) {
                            acid_shots[i] = (AcidShot){true, boss_x + cosf(a) * 100.0f,
                                boss_y + sinf(a) * 100.0f, boss_angle + sweep, 15, 5};
                            break;
                        }
                    }
#endif
#if LEVEL_BOSS_YELLOW
                    if (boss_phase == 2 && (boss_tick == 1 || boss_tick == 42)) {
                        float a = boss_angle * (3.14159265f / 180.0f);
                        for (int i = 0; i < MAX_ACID; i++) if (!acid_shots[i].active) {
                            acid_shots[i] = (AcidShot){true, boss_x + cosf(a) * 100.0f,
                                boss_y + sinf(a) * 100.0f, boss_angle, 15, 3};
                            break;
                        }
                    }
#endif
                    if (++boss_tick >= duration) { boss_phase = boss_phase == 3 ? 0 : boss_phase + 1; boss_tick = 0; }
                }
                if (boss_hp > 0 && player_hp > 0 && hurt_timer == 0 && hypotf(player_x - boss_x, player_y - boss_y) < 95.0f) {
                    audio_play(SND_TREXATTACK);
                    player_hp -= BOSS_CONTACT_DAMAGE; if (player_hp < 0) player_hp = 0; hurt_timer = 32;
                }
#endif
                for (int e = 0; e < LEVEL_ENEMY_COUNT; e++) {
                    EnemySpawn *enemy = &enemies[e];
                    if (enemy->hp <= 0) {
                        if (enemy_dying[e] > 0) enemy_dying[e]--;
                        continue;
                    }
                    if (enemy_hurt[e] > 0) { enemy_hurt[e]--; continue; }
                    float near_x = enemy->x - player_x, near_y = enemy->y - player_y;
                    if (near_x * near_x + near_y * near_y > 1200.0f * 1200.0f) continue;
                    float distance2 = near_x * near_x + near_y * near_y;
                    if (enemy_hidden[e]) {
                        if (player_hp > 0 && distance2 <= 35000) {
                            enemy_hidden[e] = false;
                            enemy_hunt[e] = 1 + rand() % 75;
                            enemy_running[e] = true;
                        } else {
                            continue;
                        }
                    }
                    if ((enemy->kind == 3 || enemy->kind == 4 || enemy->kind == 6 || enemy->kind == 7 || (LEVEL_TYPHON && enemy->kind >= 8)) && player_hp > 0 && distance2 < 300.0f * 300.0f && !enemy_hunt[e])
                        enemy_hunt[e] = 1 + rand() % 30;
                    bool hunting = enemy_hunt[e] > 0;
                    if (hunting) enemy_hunt[e]--;
                    if (enemy_cooldown[e] > 0) enemy_cooldown[e]--;
                    if (enemy_recovery[e] > 0) enemy_recovery[e]--;
                    if (enemy_windup[e] > 0 && --enemy_windup[e] == 0) {
                        audio_play(enemy->kind == 10 ? SND_DINOLAZER : (LEVEL_RED_RAPTOR && enemy->kind == 7) ? SND_FLAME : SND_LEZARDJAUNE);
                        float a = enemy->angle * (3.14159265f / 180.0f);
                        for (int i = 0; i < MAX_ACID; i++) {
                            if (acid_shots[i].active) continue;
                            acid_shots[i] = (AcidShot){true, enemy->x + cosf(a) * 38.9f + (enemy->kind == 10 ? sinf(a) * 18 : 0),
                                enemy->y + sinf(a) * 38.9f - (enemy->kind == 10 ? cosf(a) * 18 : 0), enemy->angle, 25, enemy->kind == 10 ? 4 : enemy->kind == 7 ? 2 : enemy->kind == 3 ? 1 : 0};
                            break;
                        }
                        if (LEVEL_TYPHON && enemy->kind == 10) {
                            for (int i = 0; i < MAX_ACID; i++) if (!acid_shots[i].active) {
                                acid_shots[i] = (AcidShot){true, enemy->x + cosf(a) * 38.9f - sinf(a) * 18,
                                    enemy->y + sinf(a) * 38.9f + cosf(a) * 18, enemy->angle, 25, 4};
                                break;
                            }
                        }
                        enemy_recovery[e] = 12;
                    }
                    if (LEVEL_RED_RAPTOR && enemy->kind == 7 && enemy_recovery[e] > 0 && enemy_recovery[e] < 12 && enemy_recovery[e] % 2 == 0) {
                        float a = enemy->angle * (3.14159265f / 180.0f);
                        for (int i = 0; i < MAX_ACID; i++) {
                            if (acid_shots[i].active) continue;
                            acid_shots[i] = (AcidShot){true, enemy->x + cosf(a) * 38.9f,
                                enemy->y + sinf(a) * 38.9f, enemy->angle, 25, 2};
                            break;
                        }
                    }
                    float heading = enemy->angle * (3.14159265f / 180.0f);
                    float facing = cosf(heading) * -near_x + sinf(heading) * -near_y;
                    if (enemy_jump_cooldown[e] > 0) enemy_jump_cooldown[e]--;
                    if (enemy_jump[e] > 0) enemy_jump[e]--;
                    if ((enemy->kind == 4 || enemy->kind == 6 || enemy->kind == 7) && player_hp > 0 && distance2 < 250.0f * 250.0f &&
                        facing > 0 && !enemy_jump[e] && !enemy_jump_cooldown[e] && !enemy_windup[e] && !enemy_recovery[e]) {
                        enemy_jump[e] = 18;
                        enemy_jump_cooldown[e] = 90;
                    }
                    if ((enemy->kind == 2 || enemy->kind == 3 || enemy->kind == 5 || (LEVEL_RED_RAPTOR && enemy->kind == 7) || (LEVEL_TYPHON && enemy->kind == 10)) && player_hp > 0 && distance2 < 300.0f * 300.0f &&
                        facing > 0 && !enemy_cooldown[e] && !enemy_windup[e] && !enemy_recovery[e] && !enemy_jump[e]) {
                        enemy_windup[e] = 12;
                        enemy_cooldown[e] = 75;
                    }
                    if (!hunting && --enemy_timer[e] <= 0) {
                        if (enemy->kind == 1 || enemy->kind == 5) {
                            int choice = rand() % 6;
                            if (choice >= 4) {
                                enemy_hidden[e] = true;
                                enemy_running[e] = false;
                                continue;
                            }
                            enemy_running[e] = choice < 3;
                        } else {
                            enemy_running[e] = (rand() % 3) != 0;
                        }
                        enemy_timer[e] = 1 + rand() % (enemy_running[e] ? 50 : 20);
                    }
                    if ((hunting || enemy_running[e] || enemy_jump[e]) && !enemy_windup[e] && !enemy_recovery[e]) {
                        if (hunting) {
                            float target = atan2f(-near_y, -near_x) * (180.0f / 3.14159265f);
                            float error = remainderf(target - enemy->angle, 360.0f);
                            enemy->angle += fminf(6, fmaxf(-6, error));
                        } else {
                            if (--enemy_turn_timer[e] <= 0) {
                                enemy_steer[e] = rand() % 3 - 1;
                                enemy_turn_timer[e] = 1 + rand() % 15;
                            }
                            enemy->angle += enemy_steer[e] * 6.0f;
                        }
                        float a = enemy->angle * (3.14159265f / 180.0f);
                        float enemy_speed = enemy_jump[e] ? 20.0f : (enemy->kind == 4 || enemy->kind == 6 || enemy->kind == 7) ? 8.0f : 7.5f;
                        int enemy_steps = (int)ceilf(enemy_speed / 4.0f);
                        float sx = cosf(a) * enemy_speed / enemy_steps, sy = sinf(a) * enemy_speed / enemy_steps;
                        for (int step = 0; step < enemy_steps; step++) {
                            bool blocked;
#if LEVEL_TYPHON
                            if (enemy->kind >= 8) {
                                float nx = enemy->x + sx, ny = enemy->y + sy;
                                blocked = vehicle_solid(nx, ny) || vehicle_solid(nx - 12, ny) ||
                                          vehicle_solid(nx + 12, ny) || vehicle_solid(nx, ny - 12) ||
                                          vehicle_solid(nx, ny + 12);
                            } else
#endif
                                blocked = lizard_blocked(enemy->x + sx, enemy->y + sy);
                            if (!blocked) {
                                enemy->x += sx; enemy->y += sy;
                            } else {
                                enemy->angle += 90.0f;
                                enemy_turn_timer[e] = 0;
                                break;
                            }
                        }
                    }
                    if (player_hp > 0 && hurt_timer == 0 && (!LEVEL_TYPHON || enemy->kind >= 8) &&
                        lizard_touches_hammer(enemy, player_x, player_y, angle)) {
                        audio_play(LEVEL_TYPHON && enemy->kind >= 8 ? SND_PTEROCRI : enemy->kind >= 4 && enemy->kind != 5 ? SND_RAPTORATTACK : SND_LEZARDATTACK);
                        player_hp -= LEVEL_TYPHON && enemy->kind >= 8 ? enemy->kind - 5 : enemy->kind == 7 ? (LEVEL_RED_RAPTOR ? 5 : 3) : enemy->kind == 6 ? 4 : (enemy->kind == 3 || enemy->kind == 4) ? 3 : 1;
                        if (player_hp < 0) player_hp = 0;
                        hurt_timer = 32;
                    }
                }
                for (int i = 0; i < MAX_ACID; i++) {
                    AcidShot *shot = &acid_shots[i];
                    if (!shot->active) continue;
                    float target = atan2f(player_y - shot->y, player_x - shot->x) * (180.0f / 3.14159265f);
                    float error = remainderf(target - shot->angle, 360.0f);
                    if (shot->kind != 1 && shot->kind != 4 && shot->kind != 5) {
                        float turn = shot->kind == 2 ? 11.25f : 2.8125f;
                        shot->angle += fminf(turn, fmaxf(-turn, error));
                    }
                    float rad = shot->angle * (3.14159265f / 180.0f);
                    for (int step = 0; step < 2 && shot->active; step++) {
                        float step_speed = shot->kind == 5 ? 7.0f : shot->kind == 3 ? 2.0f : shot->kind == 2 ? 9.5f : shot->kind ? 10 : 5;
                        float pulse = shot->kind == 5 ? (2 * (shot->life % 6) - 3) * 2.0f : 0.0f;
                        shot->x += cosf(rad) * step_speed - sinf(rad) * pulse;
                        shot->y += sinf(rad) * step_speed + cosf(rad) * pulse;
                        if (shot->kind == 5 ? vehicle_solid(shot->x, shot->y) : (!(LEVEL_TYPHON && shot->kind == 4) && scenery_solid(shot->x, shot->y, true))) shot->active = false;
                        else if (point_hits_hammer(shot->x, shot->y, player_x, player_y, angle)) {
                            shot->active = false;
                            if (player_hp > 0 && hurt_timer == 0) {
                                player_hp -= shot->kind == 3 ? 3 : shot->kind == 5 ? 5 : shot->kind == 4 ? 5 : shot->kind == 2 ? 5 : shot->kind ? 2 : 1;
                                if (player_hp < 0) player_hp = 0;
                                hurt_timer = 32;
                            }
                        }
                    }
                    if (--shot->life <= 0) shot->active = false;
#if LEVEL_BOSS_YELLOW
                    if (!shot->active && shot->kind == 3 && rand() % 100 >= 33 && !lizard_blocked(shot->x, shot->y)) {
                        for (int e = 0; e < LEVEL_ENEMY_COUNT; e++) {
                            if (enemies[e].hp > 0 || enemy_dying[e] > 0) continue;
                            enemies[e] = (EnemySpawn){shot->x, shot->y, shot->angle, 7, 7};
                            enemy_running[e] = true; enemy_hidden[e] = false;
                            enemy_timer[e] = enemy_turn_timer[e] = enemy_steer[e] = 0;
                            enemy_hunt[e] = 75; enemy_windup[e] = enemy_recovery[e] = 0;
                            enemy_cooldown[e] = enemy_hurt[e] = 0;
                            enemy_jump[e] = enemy_jump_cooldown[e] = 0;
                            break;
                        }
                    }
#endif
                }
                for (int i = 0; i < MAX_PROJECTILES; i++) {
                    Projectile *shot = &shots[i];
                    if (!shot->active) continue;
                    if ((!LEVEL_TYPHON && shot->kind == 2) || shot->kind == 4 || (LEVEL_TYPHON && shot->kind == 1)) {
                        float best = 400.0f * 400.0f;
                        int target = -1;
                        for (int e = 0; e < LEVEL_ENEMY_COUNT; e++) {
                            if (enemies[e].hp <= 0 || enemy_hidden[e]) continue;
                            float x = enemies[e].x - shot->x, y = enemies[e].y - shot->y;
                            float d = x*x + y*y;
                            if (d < best) { best = d; target = e; }
                        }
                        #if LEVEL_HAS_BOSS
                        if (boss_hp > 0) {
                            float x = boss_x - shot->x, y = boss_y - shot->y;
                            if (x*x + y*y < best) target = -2;
                        }
#endif
                        if (target != -1) {
                            float tx, ty;
#if LEVEL_HAS_BOSS
                            if (target == -2) { tx = boss_x; ty = boss_y; }
                            else
#endif
                            { tx = enemies[target].x; ty = enemies[target].y; }
                            float a = atan2f(ty - shot->y, tx - shot->x) * (180.0f / 3.14159265f);
                            float delta = remainderf(a - shot->angle, 360.0f);
                            float turn = shot->kind == 4 ? 11.25f : 22.5f;
                            shot->angle += fminf(turn, fmaxf(-turn, delta));
                            a = shot->angle * (3.14159265f / 180.0f);
                            shot->dx = cosf(a); shot->dy = sinf(a);
                        }
                    }
                    /* Sample the path to avoid skipping narrow collision shapes. */
                    float speed = shot->kind == 0 ? 50.0f : shot->kind == 1 ? 40.0f : shot->kind == 3 || shot->kind == 4 ? 30.0f : shot->kind == 5 ? 27.0f : 28.0f;
                    for (int step = 0; step < 10 && shot->active; step++) {
                        shot->x += shot->dx * (speed / 10);
                        shot->y += shot->dy * (speed / 10);
                        int prop = prop_at(shot->x, shot->y);
                        if ((LEVEL_TYPHON && prop >= 0 && props[prop].kind < 3) || (!LEVEL_TYPHON && scenery_solid(shot->x, shot->y, true))) {
                            audio_play(SND_IMPACT);
                            if (prop >= 0) destroy_prop(prop, pickups);
                            else damage_scenery(shot->x, shot->y, shot->kind == 0 ? 1 : shot->kind == 3 || shot->kind == 4 ? 5 : 3);
                            shot->active = false;
                        }
                        if (shot->active) {
#if LEVEL_HAS_BOSS
                            if (boss_hp > 0 && hypotf(shot->x - boss_x, shot->y - boss_y) < 80.0f) {
                                shot->active = false;
                                if (boss_phase == 2) {
                                    boss_hp -= LEVEL_TYPHON ? (shot->kind == 0 ? 3 : shot->kind == 1 ? 9 : 5) : shot->kind == 0 ? 1 : (shot->kind == 3 || shot->kind == 4) ? 5 : 3;
                                    if (boss_hp <= 0) { boss_hp = 0; boss_phase = 4; boss_tick = 0; score_value += BOSS_SCORE; }
                                }
                            }
#endif
                            for (int e = 0; e < LEVEL_ENEMY_COUNT; e++) {
                                if (enemy_hit(&enemies[e], shot->x, shot->y)) {
                                    audio_play(SND_IMPACT);
                                    if (enemy_hidden[e]) {
                                        enemy_hidden[e] = false;
                                        enemy_running[e] = false;
                                        enemy_timer[e] = 15;
                                    }
                                    enemies[e].hp -= LEVEL_TYPHON ? (shot->kind == 0 ? 2 : shot->kind == 1 ? 6 : 4) : shot->kind == 0 ? 1 : shot->kind == 3 || shot->kind == 4 ? 5 : 3;
                                    if (enemies[e].hp <= 0) {
                                        enemy_dying[e] = enemy_frame_count[enemies[e].kind][5];
                                        score_value += enemy_score(enemies[e].kind);
                                    } else if (!((enemies[e].kind == 4 || enemies[e].kind == 6 || enemies[e].kind == 7) && enemy_jump[e])) {
                                        enemy_hurt[e] = enemy_frame_count[enemies[e].kind][4];
                                    }
                                    shot->active = false;
                                    break;
                                }
                            }
                        }
                    }
#if LEVEL_PREDATOR
                    /* Keep Predator shots alive until they leave the current view. */
                    if (shot->kind >= 3 &&
                        (fabsf(shot->x - cam_x) > half_view_w + 30 || fabsf(shot->y - cam_y) > VIEW_H / 2 + 30))
                        shot->active = false;
#endif
                    if (--shot->life <= 0) shot->active = false;
                }
                if (fire_cooldown > 0 && !burst_left) fire_cooldown--;
                if (player_hp > 0 && fire_press_pending) {
                    fire_press_pending = false;
                    charge_ticks = 0;
                    if (!burst_left && !fire_cooldown) {
                        burst_kind = LEVEL_PREDATOR ? 3 : 0; burst_left = LEVEL_TYPHON ? 8 : LEVEL_PREDATOR ? 1 : 6; burst_delay = 0;
                        fire_cooldown = LEVEL_PREDATOR ? 12 : 7;
                    }
                }
                if (fire_down && charge_ticks < 60) {
                    charge_ticks++;
                    if (charge_ticks == 29 && weapon_level > 0) audio_play(SND_CHARGE);
                }
                if (fire_release_pending) {
                    fire_release_pending = false;
                    int charge = weapon_level >= 2 && charge_ticks >= 55 ? 2 :
                                 weapon_level >= 1 && charge_ticks >= 29 ? 1 : 0;
                    charge_ticks = 0;
                    if (player_hp > 0 && charge > 0) {
                        audio_play(LEVEL_PREDATOR ? (charge == 1 ? SND_SPIRALE : SND_MITRAILLE) : LEVEL_TYPHON ? SND_LAZER : SND_SPIRALE);
                        burst_kind = LEVEL_PREDATOR ? charge + 3 : charge;
                        burst_left = LEVEL_PREDATOR ? (charge == 1 ? 5 : 30) : (LEVEL_TYPHON ? (charge == 1 ? 12 : 24) : (charge == 1 ? 8 : 4));
                        burst_delay = 0;
                    } else if (player_hp > 0 && !burst_left && !fire_cooldown) {
                        burst_kind = LEVEL_PREDATOR ? 3 : 0; burst_left = LEVEL_TYPHON ? 8 : LEVEL_PREDATOR ? 1 : 6; burst_delay = 0; fire_cooldown = LEVEL_PREDATOR ? 12 : 7;
                    }
                }
                if (player_hp > 0 && burst_left > 0) {
                    if (burst_delay > 0) burst_delay--;
                    else {
                        for (int i = 0; i < MAX_PROJECTILES; i++) {
                            if (shots[i].active) continue;
                            float fire_angle = angle * (3.14159265f / 180.0f);
                            float fx = cosf(fire_angle), fy = sinf(fire_angle);
                            float side = burst_kind == 0 ? gun_side * 8 : 0;
#if LEVEL_TYPHON
                            float muzzle_x = burst_kind == 0 ? TYPHON_MCSHOOT0_0_X : burst_kind == 1 ? TYPHON_MCSHOOT1_X : TYPHON_MCSHOOT2_X;
                            float muzzle_y = burst_kind == 0 ? gun_side * TYPHON_MCSHOOT0_1_Y : 0;
                            float shot_x = player_x + fx * muzzle_x - fy * muzzle_y;
                            float shot_y = player_y + fy * muzzle_x + fx * muzzle_y;
#elif LEVEL_PREDATOR
                            float muzzle_x = TURRET_X + GUN_X, muzzle_y = TURRET_Y + GUN_Y;
                            float shot_x = player_x + fx * muzzle_x - fy * muzzle_y;
                            float shot_y = player_y + fy * muzzle_x + fx * muzzle_y;
#else
                            float shot_x = player_x + fx * 32 - fy * side;
                            float shot_y = player_y + fy * 32 + fx * side;
#endif
                            shots[i] = (Projectile){true,
                                shot_x, shot_y, fx, fy, angle, LEVEL_PREDATOR ? 180 : 36, burst_kind};
                            gun_side = -gun_side;
                            if ((burst_kind == 0 && burst_left == (LEVEL_TYPHON ? 8 : 6)) || burst_kind == 3)
                                audio_play(LEVEL_PREDATOR ? SND_TANKSHOOT : SND_PLASMA);
                            burst_left--;
                            burst_delay = burst_kind == 1 ? 4 : burst_kind == 2 || burst_kind == 4 ? 5 : burst_kind == 5 ? 1 : 0;
                            break;
                        }
                    }
                }
                if (player_hp < old_hp) audio_play(player_hp <= 0 ? SND_EXPLO : SND_IMPACT);
#if LEVEL_HAS_BOSS
                if (old_boss_phase != boss_phase && boss_phase == 2) audio_play(SND_TREXCRI);
#if LEVEL_BOSS_RED
                if (old_boss_phase != boss_phase && boss_phase == 2) audio_play(SND_FLAME);
#endif
                if (old_boss_phase != boss_phase && boss_phase == 4) audio_play(SND_TREXDIE);
#endif
                accumulator -= 1.0 / 24.0;
            }
            cam_x = fminf(fmaxf(player_x, half_view_w), LEVEL_COLS * 100 - half_view_w);
            cam_y = fminf(fmaxf(player_y, 250), LEVEL_ROWS * 100 - 250);
        } else {
            accumulator = 0;
            fire_press_pending = fire_release_pending = false;
            charge_ticks = 0;
        }
        if (map_mode == 3 && player_hp > 0 && !level_won && now - last_save_ms >= 5000) {
            save_error = !checkpoint_write(player_x, player_y, angle, player_hp, eggs, weapon_level, bombs,
                                           score_value, enemies, pickups, enemy_hidden);
            resume_available = checkpoint_read(); last_save_ms = now;
        }
        int anim = ok ? (int)((osGetTime() * 24 / 1000) % i_wait_n) : 0; /* 24 fps */

        C3D_FrameBegin(C3D_FRAME_SYNCDRAW);
        C2D_TargetClear(top, C2D_Color32(34, 32, 52, 255));
        C2D_SceneBegin(top);
        if (map_mode) {
            /* Mode 1 displays baked terrain; mode 2 displays tile IDs as colors. */
            float left = cam_x - half_view_w, top_y = cam_y - VIEW_H / 2;
            /* Include an extra cell beyond each screen edge for overhanging art. */
            int first_x = (int)floorf(left / 100.0f) - 1;
            int first_y = (int)floorf(top_y / 100.0f) - 1;
            int last_x = (int)floorf((left + 400.0f / vscale) / 100.0f) + 1;
            int last_y = (int)floorf((top_y + 240.0f / vscale) / 100.0f) + 1;
            for (int j = first_y; j <= last_y && j < LEVEL_ROWS; j++)
                for (int i = first_x; i <= last_x && i < LEVEL_COLS; i++) {
                    if (i < 0 || j < 0) continue;
                    unsigned id = background_tiles[j * LEVEL_COLS + i];
                    float x = (i * 100 - left) * vscale;
                    float y = (j * 100 - top_y) * vscale;
                    if (map_mode == 1 || map_mode == 3) {
                        int idx = id <= LEVEL_MAX_TILE ? i_tiles[id] : -1;
                        if (idx >= 0) {
                            const Gfx *tile = &GFX[idx];
                            /* Slight overlap hides rasterization gaps between adjoining terrain cells. */
                            float overlap = tile->ox == 0 && tile->oy == 0 && tile->fw == 100 && tile->fh == 100 ? 0.5f : 0.0f;
                            C2D_DrawImageAt(g_imgs[idx], x + tile->ox * vscale,
                                            y + tile->oy * vscale, 0, NULL,
                                            (tile->fw * vscale + overlap) / tile->w,
                                            (tile->fh * vscale + overlap) / tile->h);
                        }
                        continue;
                    }
                    u32 color = C2D_Color32(40 + (id * 53) % 155,
                                            40 + (id * 97) % 155,
                                            40 + (id * 31) % 155, 255);
                    float right = x + 100 * vscale - 1, bottom_y = y + 100 * vscale - 1;
                    if (x < 0) x = 0;
                    if (y < 0) y = 0;
                    if (right > 400) right = 400;
                    if (bottom_y > 240) bottom_y = 240;
                    if (right > x && bottom_y > y)
                        C2D_DrawRectSolid(x, y, 0, right - x, bottom_y - y, color);
                }
            if (map_mode == 3 && ok) {
                for (int p = 0; p < LEVEL_PROP_COUNT; p++) {
                    const Prop *prop = &props[p];
                    if (!prop->active || i_prop[prop->kind] < 0) continue;
                    float x = (prop->x - left) * vscale, y = (prop->y - top_y) * vscale;
                    if (x < -50 || x > 450 || y < -50 || y > 290) continue;
                    int idx = i_prop[prop->kind]; const Gfx *g = &GFX[idx];
                    C2D_DrawParams params = {{x, y, g->fw * vscale, g->fh * vscale},
                        {(prop_origin_x[prop->kind] - g->ox) * vscale,
                         (prop_origin_y[prop->kind] - g->oy) * vscale},
                        0, prop->angle * (3.14159265f / 180.0f)};
                    C2D_DrawImage(g_imgs[idx], &params, NULL);
                }
            }
            if (map_mode == 3 && ok) {
                for (int p = 0; p < LEVEL_PICKUP_COUNT; p++) {
                    const Pickup *pickup = &pickups[p];
                    if (!pickup->active) continue;
                    float x = (pickup->x - left) * vscale, y = (pickup->y - top_y) * vscale;
                    if (x < -50 || x > 450 || y < -50 || y > 290) continue;
                    int kind = pickup->kind, idx = i_pickup[kind];
                    const Gfx *g = &GFX[idx];
                    C2D_DrawParams params = {{x, y, g->fw * vscale, g->fh * vscale},
                        {(pickup_origin_x[kind] - g->ox) * vscale,
                         (pickup_origin_y[kind] - g->oy) * vscale}, 0, 0};
                    C2D_DrawImage(g_imgs[idx], &params, NULL);
                }
            }
            if (map_mode == 3 && ok) {
                for (int e = 0; e < LEVEL_ENEMY_COUNT; e++) {
                    EnemySpawn *enemy = &enemies[e];
                    if ((enemy->hp <= 0 && enemy_dying[e] <= 0) || enemy_hidden[e]) continue;
                    float screen_x = (enemy->x - left) * vscale;
                    float screen_y = (enemy->y - top_y) * vscale;
                    if (screen_x < -60 || screen_x > 460 || screen_y < -60 || screen_y > 300) continue;
                    int k = enemy->kind;
                    int state = enemy_dying[e] ? 5 : enemy_hurt[e] ? 4 : enemy_jump[e] ? 6 :
                                enemy_windup[e] ? 2 : enemy_recovery[e] ? 3 :
                                (enemy_hunt[e] || enemy_running[e]) ? 1 : 0;
                    int frame;
                    if (state == 6)
                        frame = (18 - enemy_jump[e]) * enemy_frame_count[k][state] / 18;
                    else if (state == 5)
                        frame = enemy_frame_count[k][state] - enemy_dying[e];
                    else if (state == 4)
                        frame = enemy_frame_count[k][state] - enemy_hurt[e];
                    else if (state == 2)
                        frame = (12 - enemy_windup[e]) * enemy_frame_count[k][state] / 12;
                    else if (state == 3)
                        frame = (12 - enemy_recovery[e]) * enemy_frame_count[k][state] / 12;
                    else
                        frame = (int)((now * 24 / 1000) % enemy_frame_count[k][state]);
                    if (frame >= enemy_frame_count[k][state]) frame = enemy_frame_count[k][state] - 1;
                    int idx = enemy_frames[k][state][frame];
                    const Gfx *g = &GFX[idx];
                    C2D_DrawParams params = {
                        {screen_x, screen_y, g->fw * vscale, g->fh * vscale},
                        {(enemy_origin_x[k] - g->ox) * vscale,
                         (enemy_origin_y[k] - g->oy) * vscale},
                        0, enemy->angle * (3.14159265f / 180.0f)
                    };
                    C2D_DrawImage(g_imgs[idx], &params, NULL);
                }
            }
#if LEVEL_HAS_BOSS
            if (map_mode == 3 && ok && !level_won) {
                int state = boss_phase == 0 ? 0 : boss_phase == 1 ? 1 : boss_phase == 2 ? 2 : boss_phase == 3 ? 3 : 4;
                int duration = state == 0 ? 40 : state == 2 ? 82 : state == 4 ? 90 : 12;
                int frame = (state == 0 ? (int)(now * 24 / 1000) % duration : boss_tick) * boss_frame_count[state] / duration;
                if (frame >= boss_frame_count[state]) frame = boss_frame_count[state] - 1;
                int idx = boss_frames[state][frame]; const Gfx *g = &GFX[idx];
                C2D_DrawParams params = {{(boss_x - left) * vscale, (boss_y - top_y) * vscale,
                    g->fw * vscale, g->fh * vscale},
                    {(BOSS_ORIGIN_X - g->ox) * vscale, (BOSS_ORIGIN_Y - g->oy) * vscale},
                    0, boss_angle * (3.14159265f / 180.0f)};
                C2D_DrawImage(g_imgs[idx], &params, NULL);
            }
#endif
            if (map_mode == 3 && i_hammer >= 0) {
                int vehicle_image = i_hammer;
#if LEVEL_TYPHON
                vehicle_image = typhon_rotor[(now * 24 / 1000) % typhon_rotor_count];
#endif
                const Gfx *g = &GFX[vehicle_image];
                float screen_x = (player_x - left) * vscale;
                float screen_y = (player_y - top_y) * vscale;
                C2D_DrawParams params = {
                    {screen_x, screen_y, g->fw * vscale, g->fh * vscale},
                    {(HAMMER_ORIGIN_X - g->ox) * vscale,
                     (HAMMER_ORIGIN_Y - g->oy) * vscale},
                    0, angle * (3.14159265f / 180.0f)
                };
                C2D_DrawImage(g_imgs[vehicle_image], &params, NULL);
#if LEVEL_PREDATOR
                const Gfx *turret = &GFX[i_turret];
                float a = angle * (3.14159265f / 180.0f);
                float tx = TURRET_X * cosf(a) - TURRET_Y * sinf(a);
                float ty = TURRET_X * sinf(a) + TURRET_Y * cosf(a);
                C2D_DrawParams turret_params = {{screen_x + tx * vscale, screen_y + ty * vscale,
                    turret->fw * vscale, turret->fh * vscale},
                    {(TURRET_ORIGIN_X - turret->ox) * vscale, (TURRET_ORIGIN_Y - turret->oy) * vscale},
                    0, a};
                C2D_DrawImage(g_imgs[i_turret], &turret_params, NULL);
#endif
            }
            if (map_mode == 3 && i_acid >= 0) {
                for (int i = 0; i < MAX_ACID; i++) {
                    const AcidShot *shot = &acid_shots[i];
                    if (!shot->active) continue;
                    int idx = shot->kind ? i_fire : i_acid;
                    const Gfx *g = &GFX[idx];
                    float ox = shot->kind ? FIRE_ORIGIN_X : ACID_ORIGIN_X;
                    float oy = shot->kind ? FIRE_ORIGIN_Y : ACID_ORIGIN_Y;
#if LEVEL_TYPHON
                    if (shot->kind == 4) { idx = i_lazer; g = &GFX[idx]; ox = LAZER_ORIGIN_X; oy = LAZER_ORIGIN_Y; }
#endif
#if LEVEL_BOSS_RED
                    if (shot->kind == 5) {
                        int frame = (15 - shot->life) * 6 / 15;
                        if (frame < 0) frame = 0;
                        if (frame > 5) frame = 5;
                        idx = superflame_frames[frame]; g = &GFX[idx];
                        ox = superflame_ox[frame]; oy = superflame_oy[frame];
                    }
#endif
#if LEVEL_BOSS_YELLOW
                    if (shot->kind == 3) { idx = i_eggball; g = &GFX[idx]; ox = EGGBALL_ORIGIN_X; oy = EGGBALL_ORIGIN_Y; }
#endif
#if LEVEL_RED_RAPTOR
                    if (shot->kind == 2) { idx = i_flame; g = &GFX[idx]; ox = FLAME_ORIGIN_X; oy = FLAME_ORIGIN_Y; }
#endif
                    C2D_DrawParams params = {
                        {(shot->x - left) * vscale, (shot->y - top_y) * vscale,
                         g->fw * vscale, g->fh * vscale},
                        {(ox - g->ox) * vscale, (oy - g->oy) * vscale},
                        0, shot->angle * (3.14159265f / 180.0f)
                    };
                    C2D_DrawImage(g_imgs[idx], &params, NULL);
                }
            }
            if (map_mode == 3 && i_plasma >= 0) {
                for (int i = 0; i < MAX_PROJECTILES; i++) {
                    const Projectile *shot = &shots[i];
                    if (!shot->active) continue;
                    int idx = shot->kind == 0 ? i_plasma : shot->kind == 1 ? i_choc : i_intel;
                    float ox = shot->kind == 0 ? PLASMA_ORIGIN_X : shot->kind == 1 ? CHOC_ORIGIN_X : INTEL_ORIGIN_X;
                    float oy = shot->kind == 0 ? PLASMA_ORIGIN_Y : shot->kind == 1 ? CHOC_ORIGIN_Y : INTEL_ORIGIN_Y;
#if !LEVEL_PREDATOR && !LEVEL_TYPHON
                    if (shot->kind == 1 || shot->kind == 2) {
                        int kind = shot->kind - 1;
                        int frame = 36 - shot->life;
                        if (frame < 0) frame = 0;
                        if (frame > 3) frame = 3;
                        idx = car_charge_frames[kind][frame];
                        ox = car_charge_ox[kind][frame]; oy = car_charge_oy[kind][frame];
                    }
#endif
#if LEVEL_TYPHON
                    if (shot->kind == 0) { idx = i_typhon_plasma; ox = PLASMATYPHON_ORIGIN_X; oy = PLASMATYPHON_ORIGIN_Y; }
                    if (shot->kind == 1) { idx = i_typhon_intel; ox = NRGINTELTYPHON_ORIGIN_X; oy = NRGINTELTYPHON_ORIGIN_Y; }
                    if (shot->kind == 2) { idx = i_typhon_dbz; ox = DBZTYPHON_ORIGIN_X; oy = DBZTYPHON_ORIGIN_Y; }
#endif
#if LEVEL_PREDATOR
                    if (shot->kind == 3) { idx = i_nrg; ox = NRG_ORIGIN_X; oy = NRG_ORIGIN_Y; }
                    if (shot->kind == 4) { idx = i_nrgintel; ox = NRGINTEL_ORIGIN_X; oy = NRGINTEL_ORIGIN_Y; }
                    if (shot->kind == 5) { idx = i_dbz; ox = DBZ_ORIGIN_X; oy = DBZ_ORIGIN_Y; }
#endif
                    const Gfx *g = &GFX[idx];
                    C2D_DrawParams params = {
                        {(shot->x - left) * vscale, (shot->y - top_y) * vscale,
                         g->fw * vscale, g->fh * vscale},
                        {(ox - g->ox) * vscale, (oy - g->oy) * vscale},
                        0, shot->angle * (3.14159265f / 180.0f)
                    };
                    C2D_DrawImage(g_imgs[idx], &params, NULL);
                }
            }
            if (map_mode == 1 || map_mode == 3) {
                for (int j = first_y; j <= last_y && j < LEVEL_ROWS; j++)
                    for (int i = first_x; i <= last_x && i < LEVEL_COLS; i++) {
                        if (i < 0 || j < 0) continue;
                        unsigned id = foreground_tiles[j * LEVEL_COLS + i];
                        int idx = id <= LEVEL_MAX_FG ? i_foreground[id] : -1;
                        if (idx < 0) continue;
                        const Gfx *tile = &GFX[idx];
                        float x = (i * 100 - left + tile->ox) * vscale;
                        float y = (j * 100 - top_y + tile->oy) * vscale;
                        C2D_DrawImageAt(g_imgs[idx], x, y, 0, NULL,
                                        tile->fw * vscale / tile->w,
                                        tile->fh * vscale / tile->h);
                    }
            }
            if (map_mode == 2)
                C2D_DrawRectSolid(198, 118, 0, 4, 4, C2D_Color32(255, 255, 255, 255));
        } else if (ok) {
        const Gfx *zg = &GFX[i_zone];
        float zw = zg->fw * vscale, zh = zg->fh * vscale;
        float canvas_x = (400.0f - DINO_CANVAS_W * vscale) / 2.0f;
        float canvas_y = (240.0f - DINO_CANVAS_H * vscale) / 2.0f;
        float zx = canvas_x + zg->ox * vscale;
        float zy = canvas_y + zg->oy * vscale;
        if (show_zone)
            C2D_DrawImageAt(g_imgs[i_zone], zx, zy, 0.0f, NULL, zw / zg->w,
                            zh / zg->h);
        const Gfx *g = &GFX[i_wait0 + anim];
        float w = g->fw * vscale, h = g->fh * vscale;
        float ox = g->ox * vscale, oy = g->oy * vscale;
        float x = canvas_x + ox;
        float y = canvas_y + oy;
        C2D_DrawImageAt(g_imgs[i_wait0 + anim], x, y, 0.0f, NULL, w / g->w,
                        h / g->h);
        }
        if (map_mode == 3 && bomb_flash > 0) {
            u8 alpha = (u8)(bomb_flash * 5);
            C2D_DrawRectSolid(0, 0, 0, 400, 240, C2D_Color32(255, 238, 160, alpha));
        }
        C2D_Flush();
        C2D_TargetClear(bottom, C2D_Color32(20, 24, 31, 255));
        C2D_SceneBegin(bottom);
        if (ok) {
            const Gfx *radar = &GFX[i_radar];
            const Gfx *health = &GFX[i_health];

            C2D_DrawImageAt(g_imgs[i_radar], 12, 12, 0, NULL,
                            100.0f / radar->w, 100.0f / radar->h);
            if (map_mode == 3) {
#if LEVEL_HAS_BOSS
                if (boss_hp > 0) {
                    float dx = boss_x - player_x, dy = boss_y - player_y;
                    if (dx * dx + dy * dy <= 900.0f * 900.0f)
                        C2D_DrawCircleSolid(62 + dx / 20.0f, 62 + dy / 20.0f, 0, 3.0f,
                                            C2D_Color32(230, 40, 30, 255));
                }
#endif
                for (int e = 0; e < LEVEL_ENEMY_COUNT; e++) {
                    if (enemies[e].hp <= 0 || enemy_hidden[e]) continue;
                    float dx = enemies[e].x - player_x, dy = enemies[e].y - player_y;
                    if (dx * dx + dy * dy <= 900.0f * 900.0f)
                        C2D_DrawCircleSolid(62 + dx / 20.0f, 62 + dy / 20.0f, 0, 2.0f,
                                            C2D_Color32(230, 40, 30, 255));
                }
                for (int p = 0; p < LEVEL_PICKUP_COUNT; p++) {
                    if (!pickups[p].active || pickups[p].kind != 2) continue;
                    float dx = pickups[p].x - player_x, dy = pickups[p].y - player_y;
                    if (dx * dx + dy * dy <= 900.0f * 900.0f)
                        C2D_DrawCircleSolid(62 + dx / 20.0f, 62 + dy / 20.0f, 0, 2.0f,
                                            C2D_Color32(250, 210, 20, 255));
                }
            }
            C2D_DrawImageAt(g_imgs[i_health], 138, 24, 0, NULL,
                            162.0f / health->w, 23.0f / health->h);
            C2D_DrawRectSolid(145, 30, 0, 148, 11, C2D_Color32(45, 27, 25, 255));
            if (player_hp > 0)
                C2D_DrawRectSolid(145, 30, 0, 148.0f * player_hp / PLAYER_MAX_HP, 11,
                                  C2D_Color32(255, 112, 46, 255));
            if (weapon_level > 0) {
                C2D_DrawRectSolid(145, 51, 0, 148, 5, C2D_Color32(50, 50, 50, 255));
                float charge_fraction = fminf(1.0f, charge_ticks / (weapon_level >= 2 ? 55.0f : 29.0f));
                if (charge_fraction > 0)
                    C2D_DrawRectSolid(145, 51, 0, 148 * charge_fraction, 5, C2D_Color32(80, 210, 255, 255));
            }
#if LEVEL_HAS_BOSS
            C2D_DrawRectSolid(145, 115, 0, 148, 8, C2D_Color32(50, 30, 30, 255));
            if (boss_hp > 0) C2D_DrawRectSolid(145, 115, 0, 148.0f * boss_hp / (float)BOSS_MAX_HP, 8,
                                               C2D_Color32(210, 55, 50, 255));
            if (hud_buf) {
                C2D_Text hint;
                C2D_TextParse(&hint, hud_buf, "T. REX: SHOOT DURING ROAR");
                C2D_DrawText(&hint, C2D_WithColor, 134, 125, 0, 0.30f, 0.30f,
                             C2D_Color32(255, 210, 190, 255));
            }
#endif
            if (player_hp <= 0 && text_buf)
                C2D_DrawText(&disabled_text, C2D_WithColor, 16, 140, 0, 0.43f, 0.43f,
                             C2D_Color32(255, 255, 255, 255));
            if (level_won && text_buf)
                C2D_DrawText(&won_text, C2D_WithColor, 16, 140, 0, 0.43f, 0.43f,
                             C2D_Color32(255, 255, 255, 255));
#ifdef DINO_CAMPAIGN
            if (level_won && !completion_recorded && text_buf) {
                C2D_Text warning;
                C2D_TextParse(&warning, text_buf, "Save failed. Check SD card.");
                C2D_DrawText(&warning, C2D_WithColor, 16, 165, 0, 0.4f, 0.4f, C2D_Color32(255, 170, 120, 255));
            }
#endif
            if (hud_buf) {
                char info[96]; C2D_Text hud;
                C2D_TextBufClear(hud_buf);
                int killed = 0;
                for (int e = 0; e < LEVEL_ENEMY_COUNT; e++) if (enemies[e].hp <= 0) killed++;
                #if LEVEL_BOSS_YELLOW
                snprintf(info, sizeof(info), "SCORE %08u\nEGGS %d/%d  WEAPON %d\nRAPTORS %d/%d  BOMBS %d",
                         score_value, eggs, LEVEL_EGG_TOTAL, weapon_level, LEVEL_ENEMY_COUNT - killed, LEVEL_ENEMY_COUNT, bombs);
#else
                snprintf(info, sizeof(info), "SCORE %08u\nEGGS %d/%d  WEAPON %d\nDINOS %d/%d  BOMBS %d",
                         score_value, eggs, LEVEL_EGG_TOTAL, weapon_level, killed, LEVEL_ENEMY_COUNT, bombs);
#endif
                C2D_TextParse(&hud, hud_buf, info);
                C2D_TextOptimize(&hud);
                C2D_DrawText(&hud, C2D_WithColor, 135, 65, 0, 0.35f, 0.35f,
                             C2D_Color32(255, 255, 255, 255));
            }
        }
        C2D_Flush();
        C3D_FrameEnd(0);
    }

    for (int i = 0; i < GFX_SHEETS; i++)
        if (g_sheets[i]) C2D_SpriteSheetFree(g_sheets[i]);
    audio_shutdown();
    if (menu_buf) C2D_TextBufDelete(menu_buf);
    if (hud_buf) C2D_TextBufDelete(hud_buf);
    if (text_buf) C2D_TextBufDelete(text_buf);
    C2D_Fini();
    C3D_Fini();
    gfxExit();
#ifdef DINO_CAMPAIGN
    return system_exit ? -1 : campaign_advance ? 1 : 0;
#elif defined(DINO_TEST_BUILD)
    return system_exit ? -1 : 0;
#else
    (void)system_exit;
    return 0;
#endif
}
