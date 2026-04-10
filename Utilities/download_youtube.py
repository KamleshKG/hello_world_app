import yt_dlp


def download_content():
    url = input("Enter the URL (YouTube/FB): ")
    choice = input("Download as (1) Video or (2) Audio? (Enter 1 or 2): ")

    common_opts = {
        # File name short ani safe karnyasathi
        'outtmpl': '%(title).50s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
    }

    if choice == '1':
        ydl_opts = {
            **common_opts,
            'format': 'best[ext=mp4]/best',
        }
        print("\nDownloading Video...")

    elif choice == '2':
        ydl_opts = {
            **common_opts,
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
        }
        print("\nDownloading Audio...")
    else:
        return

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print("\nSuccess! Atala file download hoil.")
    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    download_content()