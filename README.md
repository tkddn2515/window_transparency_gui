# Chrome Transparency GUI

This is a simple GUI application to control the transparency of Google Chrome windows on Windows.

## 빌드 방법 (How to Build)

이 애플리케이션을 `.exe` 실행 파일로 빌드하려면 다음 단계를 따르세요.

### 1. 가상 환경 생성 및 활성화 (Create and Activate Virtual Environment)

프로젝트 폴더에서 다음 명령을 실행하여 Python 가상 환경을 생성하고 활성화합니다. 이미 가상 환경이 있다면 활성화 단계만 진행하세요.

```bash
# 1. 가상 환경 생성 (Create virtual environment)
# 시스템에 설치된 Python 버전에 따라 python 또는 python3를 사용하세요.
python -m venv venv

# 2. 가상 환경 활성화 (Activate virtual environment on Windows)
.\venv\Scripts\activate
```

### 2. 필요 패키지 설치 (Install Dependencies)

가상 환경이 활성화된 상태에서, `requirements.txt` 파일에 명시된 패키지를 설치합니다.

```bash
pip install -r requirements.txt
```

### 3. 실행 파일 빌드 (Build the Executable)

`pyinstaller`를 사용하여 `.py` 파일을 `.exe` 실행 파일로 빌드합니다.

```bash
pyinstaller --onefile --windowed --name ChromeTransparencyGUI chrome_transparency_gui.py
```

**빌드 옵션 설명:**
*   `--onefile`: 모든 파일을 하나의 실행 파일로 묶습니다.
*   `--windowed`: 실행 시 콘솔 창(검은 창)이 나타나지 않도록 합니다.
*   `--name ChromeTransparencyGUI`: 생성될 실행 파일의 이름을 `ChromeTransparencyGUI.exe`로 지정합니다.

### 4. 빌드 결과 확인 (Check the Result)

빌드가 성공적으로 완료되면, 프로젝트 폴더 내에 `dist` 폴더가 생성됩니다. 이 폴더 안에 최종 결과물인 `ChromeTransparencyGUI.exe` 파일이 있습니다.
