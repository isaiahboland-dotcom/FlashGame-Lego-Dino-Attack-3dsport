#pragma once
#include <stdbool.h>
typedef enum {
    SND_THEME, SND_MOTOR, SND_TANKMOTOR, SND_HELICO, SND_PLASMA, SND_TANKSHOOT,
    SND_LAZER, SND_SPIRALE, SND_MITRAILLE, SND_TIRSPECIAL, SND_BONUS,
    SND_BONUS_EGG, SND_BONUS_EGG_ALL, SND_CAISSE, SND_EXPLO, SND_IMPACT,
    SND_LEZARDATTACK, SND_RAPTORATTACK, SND_PTEROCRI, SND_LEZARDJAUNE,
    SND_FLAME, SND_DINOLAZER, SND_TREXCRI, SND_TREXDIE, SND_TREXATTACK,
    SND_CHARGE, SND_ACCEL, SND_ACCEL_TANK, SND_COUNT
} AudioSound;
void audio_init(void);
void audio_shutdown(void);
void audio_menu(bool playing);
void audio_engine(int vehicle, bool moving, bool playing);
void audio_play(AudioSound sound);
