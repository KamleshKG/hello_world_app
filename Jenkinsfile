pipeline {
    agent any
    environment {
        // Essential paths (modify as needed)
        FLUTTER_HOME = '/opt/flutter'
        ANDROID_HOME = '/home/vagrant/VirtualBox/android-sdk'
        PUB_CACHE = "${WORKSPACE}/.pub-cache"
        
        // Configure PATH
        PATH = "${FLUTTER_HOME}/bin:${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:${PATH}"
    }
    stages {
        stage('Setup Environment') {
            steps {
                sh '''
                # Create clean workspace directories
                mkdir -p "${PUB_CACHE}"
                
                # Verify critical tools
                flutter doctor -v
                echo "Android SDK components:"
                ls ${ANDROID_HOME}/platform-tools/adb
                '''
            }
        }

        stage('Build APK') {
            steps {
                sh '''
                # Time the build process
                START_TIME=$(date +%s)
                
                # Clean and build with verbose logging
                flutter clean
                flutter pub get --verbose
                flutter build apk --release --verbose 2>&1 | tee build.log
                
                # Calculate duration
                END_TIME=$(date +%s)
                echo "Build completed in $((END_TIME - START_TIME)) seconds"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'build.log', fingerprint: false
                }
            }
        }

        stage('Verify Artifacts') {
            steps {
                sh '''
                # Standard APK paths to check
                APK_PATHS=(
                    "build/app/outputs/flutter-apk/app-release.apk"
                    "build/app/outputs/apk/release/app-release.apk"
                )

                # Verify APK exists
                APK_FOUND=false
                for path in "${APK_PATHS[@]}"; do
                    if [ -f "$path" ]; then
                        echo "✅ Found APK at: $path"
                        ls -lh "$path"
                        APK_FOUND=true
                        echo "$path" > apk_location.txt
                    fi
                done

                if ! $APK_FOUND; then
                    echo "❌ No APK found in standard locations!"
                    echo "=== Searching entire workspace ==="
                    find "${WORKSPACE}" -name "*.apk" -exec ls -lh {} \; || echo "No APK files found"
                    exit 1
                fi
                '''
            }
        }

        stage('Publish to Artifactory') {
            when {
                expression { fileExists('apk_location.txt') }
            }
            steps {
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    script {
                        def apkPath = readFile('apk_location.txt').trim()
                        def version = sh(script: "grep 'version:' pubspec.yaml | awk '{print \$2}'", returnStdout: true).trim()
                        def appName = sh(script: "grep 'name:' pubspec.yaml | awk '{print \$2}'", returnStdout: true).trim()

                        sh """
                        echo "Publishing ${apkPath} to Artifactory"
                        curl -H "Authorization: Bearer $TOKEN" \
                             -X PUT "${ARTIFACTORY_URL}/flutter-app-releases-generic-local/${appName}/${version}/app-release.apk" \
                             -T ${apkPath}
                        """
                    }
                }
            }
        }
    }
    post {
        always {
            sh '''
            echo "=== Final Workspace Contents ==="
            ls -laR "${WORKSPACE}/build" || echo "No build directory found"
            echo "=== Disk Usage ==="
            du -sh "${WORKSPACE}"
            '''
        }
        failure {
            archiveArtifacts artifacts: '**/*.log', fingerprint: false
            sh '''
            echo "=== Error Diagnostics ==="
            grep -i "error\\|fail\\|exception" build.log || echo "No obvious errors in logs"
            '''
        }
    }
}