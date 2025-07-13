pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        PATH = "${FLUTTER_HOME}/bin:${PATH}"
        // Temporary override for Flutter toolchain
        PUB_HOSTED_URL = 'https://pub.dartlang.org'
        ARTIFACTORY_URL = 'https://trialjq29zm.jfrog.io/artifactory'
    }
    stages {
        stage('Setup Flutter') {
            steps {
                sh '''
                # Bypass toolchain authentication
                flutter doctor -v --suppress-analytics
                '''
            }
        }
        
        stage('Build') {
            environment {
                // App-specific packages use Artifactory
                PUB_HOSTED_URL = "${ARTIFACTORY_URL}/api/pub/dart-pub-pub/"
            }
            steps {
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    sh '''
                    # Configure only for app dependencies
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
                    flutter build apk --release --no-pub
                    flutter build ios --release --no-codesign --no-pub
                    flutter build web --release --no-pub
                    '''
                }
            }
            post {
                success {
                    archiveArtifacts artifacts: 'build/app/outputs/flutter-apk/app-release.apk', fingerprint: true
                    stash includes: 'build/web/**', name: 'web-build'
                    stash includes: 'build/ios/**', name: 'ios-build'
                }
            }
        }
        
        stage('Publish APK') {
            steps {
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    sh '''
                    # Publish APK to Artifactory
                    curl -H "Authorization: Bearer $TOKEN" \
                         -X PUT "${ARTIFACTORY_URL}/flutter-app-releases-generic-local/app-release.apk" \
                         -T build/app/outputs/flutter-apk/app-release.apk
                    '''
                }
            }
        }
        
        stage('Publish Web Assets') {
            steps {
                unstash 'web-build'
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    sh '''
                    # Package and publish web assets
                    cd build/web
                    zip -r web-assets.zip .
                    curl -H "Authorization: Bearer $TOKEN" \
                         -X PUT "${ARTIFACTORY_URL}/flutter-app-releases-generic-local/web-assets.zip" \
                         -T web-assets.zip
                    '''
                }
            }
        }
        
        stage('Publish iOS Archive') {
            steps {
                unstash 'ios-build'
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    sh '''
                    # Package and publish iOS archive
                    cd build/ios
                    zip -r ios-archive.zip .
                    curl -H "Authorization: Bearer $TOKEN" \
                         -X PUT "${ARTIFACTORY_URL}/flutter-app-releases-generic-local/ios-archive.zip" \
                         -T ios-archive.zip
                    '''
                }
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
    }
}