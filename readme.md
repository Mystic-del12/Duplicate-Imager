# 🖼️ Duplicate Photo Remover: Advanced Python Utility

A potent Python-based utility designed to **locate**, **preview**, and **handle duplicate or visually similar images** within a photo collection. This tool employs robust **perceptual hashing** to identify images that are visually identical, even if they possess different file formats, sizes, or minor compression artifacts.

It is perfect for cleaning a messy photo library, performing dataset preprocessing, or organizing large camera dumps efficiently.

🛡 License

This project is distributed under the MIT License.
See LICENSE for details.

💬 Contributing

Pull requests & suggestions are welcome!
If you'd like new features (GUI, ML-based similarity, duplicate clustering, etc.), open an issue.

## ✨ Key Features

| Feature | Description |
|**🔍 Perceptual Hashing**| Finds images that look the same, regardless of file format, size, or slight edits. Uses **dHash** as the primary method with **pHash** as a fallback.  |
| **📱 Modern Format Support** | Includes support for HEIC/HEIF images (modern iPhones) using the `pillow-heif` library. |
| **🚀 Threaded Processing** | Hashing operations are implemented **multithreaded** for significantly faster processing on multi-core CPUs. |
| **📊 Progress Indicators** | Utilizes **tqdm** to provide clear, real-time progress updates during hashing and processing. |
| **🖼️ Interactive Preview** | User-friendly mode that opens duplicate images one-by-one in the default viewer, allowing for informed, manual decisions. |
| **🗂️ Flexible Handling** | Duplicates can be **moved**, **copied**, or simply **logged**. |
| **🛟 Safe Deletion** | Optional, reversible deletion capability using the `send2trash` library. |
| **📑 CSV Reporting** | Creates a comprehensive duplicate file report suitable for analysis and external management. |
| **⚙️ Automatic Selection** | Provides logic to automatically decide which file to keep (e.g., keeping the first, largest, newest, or highest `resolution` file). |
| **💾 Backup Folder** | Ability to organize and save all duplicates together by their hash into a designated backup location. |
| **🛡️ Dry Run Mode** | Safely simulates all actions without making any permanent changes. |
| **💻 Cross-platform** | Fully supported on **Windows, macOS, and Linux**. |

## 📦 Installation

To set up the Duplicate Photo Remover, follow the steps below:

### 1\) Clone the Repository

Open your terminal or command prompt and execute the following commands:

```bash
git clone https://github.com/YOUR_USERNAME/Duplicate-Imager.git
cd Duplicate-Imager
```
⭐ If you found this tool useful, please star the repository!

It helps others discover the project.

---

## ⭐ Star History

## Star History

<a href="https://www.star-history.com/?repos=Mystic-del12%2FDuplicate-Imager&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=Mystic-del12/Duplicate-Imager&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=Mystic-del12/Duplicate-Imager&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=Mystic-del12/Duplicate-Imager&type=date&legend=top-left" />
 </picture>
</a>
