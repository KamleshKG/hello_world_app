pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        PATH = "${FLUTTER_HOME}/bin:${PATH}"
        // Temporary override for Flutter toolchain
        PUB_HOSTED_URL = 'https://pub.dartlang.org' 
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
                PUB_HOSTED_URL = 'https://trialjq29zm.jfrog.io/artifactory/api/pub/dart-pub-pub/'
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
                    '''
                }
            }
        }
    }
}