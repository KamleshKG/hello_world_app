pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        PATH = "${FLUTTER_HOME}/bin:${PATH}"
        PUB_HOSTED_URL = 'https://pub.dartlang.org'
        ARTIFACTORY_URL = 'https://trialjq29zm.jfrog.io/artifactory'
        OUTPUT_DIR = 'build_output'  // Custom output directory
    }
    stages {
        stage('Setup') {
            steps {
                sh '''
                flutter doctor -v --suppress-analytics
                mkdir -p ${OUTPUT_DIR}  # Create our known output directory
                '''
            }
        }

        stage('Build') {
            environment {
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
                    
                    flutter pub get
                    flutter clean
                    flutter build apk --release --no-pub --output=${OUTPUT_DIR}/app-release.apk
                    '''
                }
            }
            post {
                success {
                    script {
                        // Verify APK exists in our known location
                        if (fileExists("${OUTPUT_DIR}/app-release.apk")) {
                            archiveArtifacts artifacts: "${OUTPUT_DIR}/app-release.apk", fingerprint: true
                            env.APK_PATH = "${OUTPUT_DIR}/app-release.apk"
                        } else {
                            // Fallback check for default location
                            def found = sh(script: 'ls build/app/outputs/flutter-apk/app-release.apk || echo ""', returnStdout: true).trim()
                            if (found) {
                                archiveArtifacts artifacts: found, fingerprint: true
                                env.APK_PATH = found
                            } else {
                                error "APK not found in either ${OUTPUT_DIR}/ or default build location"
                            }
                        }
                    }
                }
            }
        }

        stage('Publish APK') {
            when {
                expression { env.APK_PATH != null }
            }
            steps {
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    sh '''
                    echo "Publishing APK from ${APK_PATH}"
                    curl -H "Authorization: Bearer $TOKEN" \
                         -X PUT "${ARTIFACTORY_URL}/flutter-app-releases-generic-local/app-release.apk" \
                         -T ${APK_PATH}
                    '''
                }
            }
        }
    }

    post {
        always {
            sh '''
            echo "Final workspace contents:"
            ls -la
            echo "Build outputs:"
            ls -la ${OUTPUT_DIR} || echo "No output directory"
            '''
            cleanWs()
        }
    }
}