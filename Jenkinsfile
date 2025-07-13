pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        PATH = "${FLUTTER_HOME}/bin:${PATH}"
        PUB_HOSTED_URL = 'https://pub.dartlang.org'
        ARTIFACTORY_URL = 'https://trialjq29zm.jfrog.io/artifactory'
        // Try common APK output paths
        APK_PATH = 'build/app/outputs/apk/release/app-release.apk'  // Most common path
    }
    stages {
        stage('Setup Flutter') {
            steps {
                sh '''
                flutter doctor -v --suppress-analytics
                '''
            }
        }

        stage('Debug: Check Workspace') {
            steps {
                sh '''
                echo "Current workspace contents:"
                ls -la
                echo "Flutter build outputs:"
                ls -la build/ || echo "No build directory exists yet"
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
                    flutter build apk --release --no-pub
                    
                    # Debug: Show actual APK location
                    echo "Build outputs:"
                    find build/ -name "*.apk" || echo "No APK files found"
                    '''
                }
            }
            post {
                success {
                    script {
                        // Try to find the APK if not in default location
                        def apkFile = findFiles(glob: 'build/**/*.apk')[0]?.path
                        if (apkFile) {
                            echo "Found APK at: ${apkFile}"
                            env.ACTUAL_APK_PATH = apkFile
                            archiveArtifacts artifacts: apkFile, fingerprint: true
                        } else {
                            error "No APK file found in build directory. Check build logs."
                        }
                    }
                    stash includes: 'build/web/**', name: 'web-build'
                    stash includes: 'build/ios/**', name: 'ios-build'
                }
            }
        }

        stage('Publish APK') {
            steps {
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    script {
                        if (env.ACTUAL_APK_PATH) {
                            sh """
                            curl -H "Authorization: Bearer $TOKEN" \
                                 -X PUT "${ARTIFACTORY_URL}/flutter-app-releases-generic-local/app-release.apk" \
                                 -T ${env.ACTUAL_APK_PATH}
                            """
                        } else {
                            error "No APK path available for publishing"
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            sh '''
            echo "Final workspace contents:"
            ls -la
            echo "Build directory contents:"
            ls -la build/ || echo "No build directory exists"
            '''
            cleanWs()
            sh 'flutter clean'
        }
    }
}