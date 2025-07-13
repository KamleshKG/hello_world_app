pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        ANDROID_HOME = '/opt/android-sdk' // Explicitly set Android SDK path
        PATH = "${FLUTTER_HOME}/bin:${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:${PATH}"
        ARTIFACTORY_URL = 'https://trialjq29zm.jfrog.io/artifactory'
    }
    stages {
        stage('Validate Environment') {
            steps {
                script {
                    // Verify critical tools exist
                    def checks = [
                        "flutter": "which flutter",
                        "java": "java -version",
                        "android": "test -d ${ANDROID_HOME}"
                    ]
                    
                    checks.each { tool, cmd ->
                        def result = sh(script: cmd, returnStatus: true)
                        if (result != 0) {
                            error "${tool} is not properly configured. Check installation."
                        }
                    }
                    
                    // Check Flutter dependencies
                    sh '''
                    flutter doctor -v
                    flutter pub outdated --mode=null-safety
                    '''
                }
            }
        }

        stage('Resolve Dependencies') {
            steps {
                sh '''
                flutter pub upgrade --major-versions
                flutter pub get
                '''
            }
        }

        stage('Build APK') {
            environment {
                // Temporary override for build
                PUB_HOSTED_URL = "${ARTIFACTORY_URL}/api/pub/dart-pub-pub/"
            }
            steps {
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    sh '''
                    mkdir -p ~/.config/dart
                    cat > ~/.config/dart/pub-credentials.json <<EOF
                    {
                      "accessToken":"$TOKEN",
                      "refreshToken":"$TOKEN",
                      "tokenEndpoint":"$PUB_HOSTED_URL",
                      "scopes":["$PUB_HOSTED_URL"],
                      "expiration":9999999999999
                    }
                    EOF
                    
                    flutter clean
                    flutter build apk --release
                    '''
                }
            }
            post {
                success {
                    archiveArtifacts artifacts: 'build/app/outputs/flutter-apk/app-release.apk', fingerprint: true
                }
            }
        }

        stage('Publish to Artifactory') {
            when {
                expression { fileExists('build/app/outputs/flutter-apk/app-release.apk') }
            }
            steps {
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    script {
                        def version = sh(script: "cat pubspec.yaml | grep 'version:' | awk '{print \$2}'", returnStdout: true).trim()
                        def appName = sh(script: "cat pubspec.yaml | grep 'name:' | awk '{print \$2}'", returnStdout: true).trim()
                        
                        sh """
                        curl -H "Authorization: Bearer $TOKEN" \
                             -X PUT "${ARTIFACTORY_URL}/flutter-app-releases-generic-local/${appName}/${version}/app-release.apk" \
                             -T build/app/outputs/flutter-apk/app-release.apk
                        """
                    }
                }
            }
        }
    }
    post {
        always {
            sh '''
            echo "Environment Status:"
            flutter doctor -v
            echo "Build Directory Contents:"
            ls -la build/ || echo "No build directory"
            '''
        }
        failure {
            archiveArtifacts artifacts: '**/build.log', fingerprint: false
        }
    }
}