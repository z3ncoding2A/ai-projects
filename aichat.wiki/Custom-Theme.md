AIChat supports customizing the theme through the `.tmTheme` file.

## Setup the theme

Just download the `.tmTheme` file to the aichat configuration directory and name it `dark.tmTheme`/`light.tmTheme`. The theme will be automatically loaded when aichat starts.

```sh
# goto config dir
cd "$(dirname "$(aichat --info | grep config_file | awk '{print $2}')")"
# override dark theme
wget -O dark.tmTheme 'https://raw.githubusercontent.com/braver/Solarized/87e01090cf5fb821a234265b3138426ae84900e7/Solarized%20(dark).tmTheme'
# override light theme
wget -O light.tmTheme 'https://raw.githubusercontent.com/braver/Solarized/87e01090cf5fb821a234265b3138426ae84900e7/Solarized%20(light).tmTheme'
```

## Themes

### 1337-Scheme

https://raw.githubusercontent.com/MarkMichos/1337-Scheme/ca6a329cfda8307449d405b70f8fab34b8fd23b5/1337.tmTheme

![image](https://github.com/sigoden/aichat/assets/4012553/2efd7078-077f-4949-a08f-5c19c50097a7)

### Coldark

https://raw.githubusercontent.com/ArmandPhilippot/coldark-bat/e44750b2a9629dd12d8ed3ad9fd50c77232170b9/Coldark-Dark.tmTheme

![image](https://github.com/sigoden/aichat/assets/4012553/05d9b71b-3d32-4621-80f4-9676f190122c)

### Dracula

https://raw.githubusercontent.com/dracula/sublime/c2de0acf5af67042393cf70de68013153c043656/Dracula.tmTheme

![image](https://github.com/sigoden/aichat/assets/4012553/1422864d-4b25-4b4c-8eb8-34047dd5c525)

### Github

https://raw.githubusercontent.com/AlexanderEkdahl/github-sublime-theme/508740b2430c3c3a9e785fc93ee1d7c6f233af53/GitHub.tmTheme

![image](https://github.com/sigoden/aichat/assets/4012553/235343c3-9827-4a60-be3a-906c48c0b000)

### gruvbox

https://raw.githubusercontent.com/subnut/gruvbox-tmTheme/64c47250e54298b91e2cf8d401320009aba9f991/gruvbox-dark.tmTheme

![image](https://github.com/sigoden/aichat/assets/4012553/00053c50-958f-45f6-b964-d4908e87699d)

https://raw.githubusercontent.com/subnut/gruvbox-tmTheme/64c47250e54298b91e2cf8d401320009aba9f991/gruvbox-light.tmTheme

![image](https://github.com/sigoden/aichat/assets/4012553/1e9e8684-39f7-43d8-97b2-37d15385536a)

### OneHalf

https://raw.githubusercontent.com/sonph/onehalf/141c775ace6b71992305f144a8ab68e9a8ca4a25/sublimetext/OneHalfDark.tmTheme

![image](https://github.com/sigoden/aichat/assets/4012553/0ba48832-7ec0-43a8-8764-3deefa4a2197)

https://raw.githubusercontent.com/sonph/onehalf/141c775ace6b71992305f144a8ab68e9a8ca4a25/sublimetext/OneHalfLight.tmTheme

![image](https://github.com/sigoden/aichat/assets/4012553/a40f6753-0842-46ed-8721-e00b97ef955a)

### Solarized

https://raw.githubusercontent.com/braver/Solarized/87e01090cggjf5fb821a234265b3138426ae84900e7/Solarized%20(dark).tmTheme

![image](https://github.com/sigoden/aichat/assets/4012553/71cae191-cde1-428e-bed4-89e7ebea4b6d)

https://raw.githubusercontent.com/braver/Solarized/87e01090cf5fb821a234265b3138426ae84900e7/Solarized%20(light).tmTheme

![image](https://github.com/sigoden/aichat/assets/4012553/e8742540-e3b7-4eca-b3ba-f8f324624514)

### Sublime Snazzy

https://raw.githubusercontent.com/greggb/sublime-snazzy/70343201f1d7539adbba3c79e2fe81c2559a0431/Sublime%20Snazzy.tmTheme

![image](https://github.com/sigoden/aichat/assets/4012553/38481875-96a8-4b2b-9a1e-602af4f06d5b)

### TwoDark

https://raw.githubusercontent.com/erremauro/TwoDark/8e0f6fa5b59d196658a22288f519fd8320de4c87/TwoDark.tmTheme

![image](https://github.com/sigoden/aichat/assets/4012553/555b199b-7f68-43de-a71b-510f8fcdfe7c)

### Visual Studio Dark+

https://raw.githubusercontent.com/vidann1/visual-studio-dark-plus/01ee1e8e0dc578f3b4e8c0dbb6aa0279b4a26a40/Visual%20Studio%20Dark%2B.tmTheme

![image](https://github.com/sigoden/aichat/assets/4012553/d80f0068-d200-4ee2-ac22-f55133214f59)

### Zenburn

https://raw.githubusercontent.com/colinta/zenburn/86d4ee7a1f884851a1d21d66249687f527fced32/zenburn.tmTheme

![image](https://github.com/sigoden/aichat/assets/4012553/e28e6498-3ca0-46cb-aa6a-0a491e16470a)
