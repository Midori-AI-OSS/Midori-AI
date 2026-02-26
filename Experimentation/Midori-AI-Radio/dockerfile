FROM lunamidori5/pixelarch:topaz

# Android build dependencies
RUN yay -Syu --noconfirm jdk17-openjdk unzip curl git && clean-yay

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk

# Keep SDK and build caches under /tmp where practical.
# Note: Experimentation/Midori-AI-Radio/local.properties currently points sdk.dir here.
ENV ANDROID_SDK_ROOT=/tmp/agents-artifacts/android-sdk
ENV ANDROID_HOME=/tmp/agents-artifacts/android-sdk
ENV GRADLE_USER_HOME=/tmp/gradle

ENV PATH="${ANDROID_SDK_ROOT}/platform-tools:${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin:${PATH}"

# Install Android command line tools + platform tools + build tools
ARG ANDROID_CMDLINE_TOOLS_ZIP=commandlinetools-linux-11076708_latest.zip
ARG ANDROID_CMDLINE_TOOLS_URL=https://dl.google.com/android/repository/

RUN sudo mkdir -p /tmp/agents-artifacts \
    && sudo chown -R midori-ai:midori-ai /tmp/agents-artifacts \
    && mkdir -p /tmp/android-sdk-tmp \
    && curl -fsSL "${ANDROID_CMDLINE_TOOLS_URL}${ANDROID_CMDLINE_TOOLS_ZIP}" -o /tmp/android-sdk-tmp/cmdline-tools.zip \
    && rm -rf "${ANDROID_SDK_ROOT}" \
    && mkdir -p "${ANDROID_SDK_ROOT}/cmdline-tools" \
    && unzip -q /tmp/android-sdk-tmp/cmdline-tools.zip -d /tmp/android-sdk-tmp \
    && mv /tmp/android-sdk-tmp/cmdline-tools "${ANDROID_SDK_ROOT}/cmdline-tools/latest" \
    && rm -rf /tmp/android-sdk-tmp

RUN yes | sdkmanager --sdk_root="${ANDROID_SDK_ROOT}" --licenses

# Midori AI Radio uses compileSdk=34.
RUN sdkmanager --sdk_root="${ANDROID_SDK_ROOT}" \
        "platform-tools" \
        "platforms;android-34" \
        "build-tools;34.0.0"

# Container conventions:
# - bind-mount the repo at /workspace
# - mount output directory at /out
RUN sudo mkdir -p /workspace /out \
    && sudo chown -R midori-ai:midori-ai /workspace /out

RUN sudo tee /usr/local/bin/build-midoriai-radio-apk >/dev/null <<'EOF'
#!/usr/bin/env bash

set -euo pipefail

workspace_dir="${WORKSPACE:-/workspace}"
project_dir="${workspace_dir}/Experimentation/Midori-AI-Radio"
out_dir="${OUT_DIR:-/out}"

mkdir -p "${out_dir}"

cd "${project_dir}"

chmod +x ./gradlew

./gradlew :app:assembleDebug

if [ -d "app/build/outputs/apk" ]; then
  find app/build/outputs/apk -type f -name "*.apk" -print -exec cp -f {} "${out_dir}/" \;
fi
EOF

RUN sudo chmod +x /usr/local/bin/build-midoriai-radio-apk

WORKDIR /workspace
CMD ["build-midoriai-radio-apk"]
