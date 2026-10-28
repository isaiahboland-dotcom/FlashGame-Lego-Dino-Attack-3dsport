#include <3ds.h>
#include <string.h>
#include "audio.h"
#define SOUND_LIST(X) \
 X(theme) X(motor) X(tankmotor) X(helico) X(plasma) X(tankshoot) X(lazer) \
 X(spirale) X(mitraille) X(tirspecial) X(bonus) X(bonus_egg) X(bonus_egg_all) \
 X(caisse) X(explo) X(impact) X(lezardattack) X(raptorattack) X(pterocri) \
 X(lezardjaune) X(flame) X(dinolazer) X(trexcri) X(trexdie) X(trexattack) X(charge) \
 X(accel) X(accel_tank)
#define DECLARE(n) extern const u8 snd_##n##_pcm[]; extern const u32 snd_##n##_pcm_size;
SOUND_LIST(DECLARE)
#define DATA(n) snd_##n##_pcm,
#define SIZE(n) &snd_##n##_pcm_size,
static const u8 *const raw[] = { SOUND_LIST(DATA) };
static const u32 *const sizes[] = { SOUND_LIST(SIZE) };
static void *samples[SND_COUNT];
static ndspWaveBuf waves[16];
static bool ready, menu_playing, engine_moving;
static int engine = -1;
static void configure(int channel, float volume) {
    float mix[12] = {0}; mix[0] = mix[1] = volume;
    ndspChnReset(channel); ndspChnSetInterp(channel, NDSP_INTERP_LINEAR);
    ndspChnSetRate(channel, 22050.0f); ndspChnSetFormat(channel, NDSP_FORMAT_MONO_PCM16);
    ndspChnSetMix(channel, mix);
}
void audio_init(void) {
    ready = false; menu_playing = false; engine_moving = false; engine = -1;
    memset(samples, 0, sizeof(samples)); memset(waves, 0, sizeof(waves));
    if (R_FAILED(ndspInit())) return;
    ndspSetOutputMode(NDSP_OUTPUT_STEREO);
    for (int i = 0; i < SND_COUNT; i++) {
        samples[i] = linearAlloc(*sizes[i]);
        if (!samples[i]) {
            for (int j = 0; j < i; j++) linearFree(samples[j]);
            memset(samples, 0, sizeof(samples)); ndspExit(); return;
        }
        memcpy(samples[i], raw[i], *sizes[i]); DSP_FlushDataCache(samples[i], *sizes[i]);
    }
    ready = true;
}
static void start(int channel, AudioSound sound, float volume, bool loop) {
    ndspChnWaveBufClear(channel); configure(channel, volume);
    memset(&waves[channel], 0, sizeof(waves[channel]));
    waves[channel].data_vaddr = samples[sound]; waves[channel].nsamples = *sizes[sound] / 2;
    waves[channel].looping = loop; ndspChnWaveBufAdd(channel, &waves[channel]);
}
void audio_menu(bool playing) {
    if (!ready || playing == menu_playing) return;
    if (playing) start(0, SND_THEME, 0.32f, true); else ndspChnWaveBufClear(0);
    menu_playing = playing;
}
void audio_engine(int vehicle, bool moving, bool playing) {
    if (!ready) return;
    if (!playing) { if (engine >= 0) ndspChnWaveBufClear(1); engine = -1; engine_moving = false; return; }
    if (vehicle != engine) {
        engine = vehicle;
        engine_moving = false;
        start(1, vehicle == 2 ? SND_HELICO : vehicle == 1 ? SND_TANKMOTOR : SND_MOTOR, 0.16f, true);
    }
    if (moving && !engine_moving && vehicle != 2)
        audio_play(vehicle == 1 ? SND_ACCEL_TANK : SND_ACCEL);
    engine_moving = moving;
    float volume = moving ? 0.23f : 0.12f;
    float mix[12] = {0}; mix[0] = mix[1] = volume; ndspChnSetMix(1, mix);
}
void audio_play(AudioSound sound) {
    if (!ready || sound < 0 || sound >= SND_COUNT) return;
    for (int i = 2; i < 16; i++) {
        if (waves[i].status == NDSP_WBUF_FREE || waves[i].status == NDSP_WBUF_DONE) {
            start(i, sound, 0.55f, false); return;
        }
    }
}
void audio_shutdown(void) {
    if (!ready) return;
    for (int i = 0; i < 16; i++) ndspChnWaveBufClear(i);
    ndspExit();
    for (int i = 0; i < SND_COUNT; i++) { linearFree(samples[i]); samples[i] = NULL; }
    ready = false;
}
