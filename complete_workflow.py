"""
완전 자동화 워크플로우: Export → Baseline Correction → Peak Detection → Quantification → Visualization
"""
import subprocess
import sys
from pathlib import Path
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import ttk
from PIL import Image
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from quantify_peaks import PeakQuantifier


class WorkflowManager:
    """완전 자동화 워크플로우 관리자"""

    def __init__(self):
        self.output_folder = None
        self.quantification_results = None

    def run_export(self, mode='interactive'):
        """
        1단계: Chemstation에서 데이터 export

        Args:
            mode: 'interactive' (대화형), 'path' (직접 경로), 'scan' (전체 스캔)
        """
        print("\n" + "="*80)
        print("1단계: Chemstation 데이터 Export")
        print("="*80)

        # auto_export_keyboard_final.py 실행
        try:
            result = subprocess.run(
                [sys.executable, 'auto_export_keyboard_final.py'],
                cwd=Path(__file__).parent,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )

            # 출력 폴더 경로 추출
            output_lines = result.stdout.split('\n')
            for line in output_lines:
                if 'result\\' in line or 'result/' in line:
                    # result/폴더명 추출
                    if 'DEF_LC' in line or 'result' in line.lower():
                        parts = line.split('result')
                        if len(parts) > 1:
                            folder_part = parts[1].strip('\\/').split()[0]
                            self.output_folder = Path('result') / folder_part
                            break

            print(f"\n[OK] Export 완료")
            if self.output_folder:
                print(f"  출력 폴더: {self.output_folder}")

            return True

        except Exception as e:
            print(f"[ERROR] Export 실패: {e}")
            return False

    def run_quantification(self, folder_path=None):
        """
        2단계: 피크 검출 및 정량 분석
        """
        if folder_path is None:
            folder_path = self.output_folder

        if folder_path is None:
            print("[ERROR] 분석할 폴더가 지정되지 않았습니다.")
            return False

        print("\n" + "="*80)
        print("2단계: 베이스라인 보정 + 피크 검출 + 정량 분석")
        print("="*80)

        try:
            quantifier = PeakQuantifier()

            # 폴더 분석
            df = quantifier.analyze_folder(folder_path)

            if len(df) > 0:
                # 리포트 생성
                output_dir = Path(folder_path) / 'quantification'
                reference_y0 = 2173.0209
                reference_a = 52004.0462
                quantifier.create_summary_report(df, output_dir, reference_y0, reference_a)

                # STD 샘플 여부 확인
                is_std_samples = df['sample'].str.contains('STD', case=False, na=False).any()

                # 개별 크로마토그램 파일 목록
                chromatogram_dir = output_dir / 'chromatograms'
                chromatogram_files = sorted(chromatogram_dir.glob('*.png')) if chromatogram_dir.exists() else []

                # 오버레이 크로마토그램 파일 목록
                overlay_dir = output_dir / 'overlays'
                overlay_files = sorted(overlay_dir.glob('*.png')) if overlay_dir.exists() else []

                self.quantification_results = {
                    'df': df,
                    'output_dir': output_dir,
                    'is_std_samples': is_std_samples,
                    'summary_csv': output_dir / 'peak_area_summary.csv' if is_std_samples else None,
                    'calibration_plot': output_dir / 'calibration_curve.png' if is_std_samples else output_dir / 'peak_information_summary.png',
                    'detailed_csv': output_dir / 'all_peaks_detailed.csv',
                    'chromatogram_files': chromatogram_files,
                    'overlay_files': overlay_files
                }

                print(f"\n[OK] 정량 분석 완료")
                print(f"  결과 저장 위치: {output_dir}")
                return True
            else:
                print("[ERROR] 분석된 데이터가 없습니다.")
                return False

        except Exception as e:
            print(f"[ERROR] 정량 분석 실패: {e}")
            import traceback
            traceback.print_exc()
            return False

    def show_results_viewer(self):
        """
        3단계: 결과 시각화 창 표시
        """
        if self.quantification_results is None:
            print("[ERROR] 표시할 결과가 없습니다.")
            return

        print("\n" + "="*80)
        print("3단계: 결과 시각화")
        print("="*80)

        # Tkinter 창 생성
        root = tk.Tk()
        root.title("HPLC 정량 분석 결과")
        root.geometry("1400x900")

        # 노트북 (탭) 생성
        notebook = ttk.Notebook(root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # STD 샘플 여부에 따라 다른 탭 구성
        is_std = self.quantification_results.get('is_std_samples', False)

        if is_std:
            # STD 샘플: 검량선 + 요약 표
            self._create_calibration_tab(notebook)
            self._create_summary_tab(notebook)
        else:
            # 일반 샘플: 피크 정보 요약
            self._create_peak_info_tab(notebook)

        # 개별 크로마토그램 탭 (공통)
        self._create_chromatograms_tab(notebook)

        # 오버레이 크로마토그램 탭 (공통)
        self._create_overlay_tab(notebook)

        # 상세 데이터 탭 (공통)
        self._create_detailed_tab(notebook)

        # 하단 버튼
        button_frame = ttk.Frame(root)
        button_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(
            button_frame,
            text="폴더 열기",
            command=lambda: self._open_folder(self.quantification_results['output_dir'])
        ).pack(side='left', padx=5)

        ttk.Button(
            button_frame,
            text="닫기",
            command=root.destroy
        ).pack(side='right', padx=5)

        print("[OK] 시각화 창을 표시합니다...")
        root.mainloop()

    def _create_calibration_tab(self, notebook):
        """검량선 탭 생성"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="검량선 (Calibration Curve)")

        # 이미지 로드
        calibration_img = self.quantification_results['calibration_plot']
        if calibration_img.exists():
            img = Image.open(calibration_img)

            # matplotlib Figure로 표시
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.imshow(np.array(img))
            ax.axis('off')

            canvas = FigureCanvasTkAgg(fig, master=tab)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

            plt.close(fig)

    def _create_peak_info_tab(self, notebook):
        """피크 정보 탭 생성 (일반 샘플용)"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="피크 정보 요약")

        # 이미지 로드
        peak_info_img = self.quantification_results['calibration_plot']
        if peak_info_img.exists():
            img = Image.open(peak_info_img)

            # matplotlib Figure로 표시
            fig, ax = plt.subplots(figsize=(12, 8))
            ax.imshow(np.array(img))
            ax.axis('off')

            canvas = FigureCanvasTkAgg(fig, master=tab)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

            plt.close(fig)

    def _create_summary_tab(self, notebook):
        """요약 표 탭 생성"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="농도별 요약")

        # 스크롤 가능한 프레임
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # CSV 데이터 읽기
        import pandas as pd
        summary_df = pd.read_csv(self.quantification_results['summary_csv'], encoding='utf-8-sig')

        # 표 생성
        tree = ttk.Treeview(scrollable_frame, columns=list(summary_df.columns), show='headings', height=15)

        # 컬럼 헤더
        for col in summary_df.columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)

        # 데이터 삽입
        for idx, row in summary_df.iterrows():
            tree.insert('', 'end', values=list(row))

        tree.pack(fill='both', expand=True, padx=10, pady=10)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _create_chromatograms_tab(self, notebook):
        """개별 크로마토그램 탭 생성"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="개별 크로마토그램")

        chromatogram_files = self.quantification_results.get('chromatogram_files', [])

        if len(chromatogram_files) == 0:
            # 크로마토그램이 없는 경우
            label = ttk.Label(tab, text="생성된 크로마토그램이 없습니다.", font=('Arial', 12))
            label.pack(expand=True)
            return

        # 좌측: 샘플 목록
        left_frame = ttk.Frame(tab, width=200)
        left_frame.pack(side='left', fill='y', padx=5, pady=5)

        ttk.Label(left_frame, text="샘플 선택:", font=('Arial', 11, 'bold')).pack(pady=5)

        # 리스트박스 + 스크롤바
        scrollbar = ttk.Scrollbar(left_frame)
        scrollbar.pack(side='right', fill='y')

        listbox = tk.Listbox(left_frame, yscrollcommand=scrollbar.set, font=('Arial', 9))
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=listbox.yview)

        # 샘플명 추가
        for file_path in chromatogram_files:
            sample_name = file_path.stem.replace('_chromatogram', '')
            listbox.insert(tk.END, sample_name)

        # 우측: 크로마토그램 표시 영역
        right_frame = ttk.Frame(tab)
        right_frame.pack(side='right', fill='both', expand=True, padx=5, pady=5)

        # 캔버스 생성
        canvas_frame = ttk.Frame(right_frame)
        canvas_frame.pack(fill='both', expand=True)

        # 초기 이미지 표시
        current_image = {'fig': None, 'canvas': None}

        def show_chromatogram(event=None):
            """선택된 크로마토그램 표시"""
            selection = listbox.curselection()
            if not selection:
                return

            idx = selection[0]
            img_path = chromatogram_files[idx]

            # 기존 캔버스 제거
            if current_image['canvas']:
                current_image['canvas'].get_tk_widget().destroy()
            if current_image['fig']:
                plt.close(current_image['fig'])

            # 이미지 로드
            img = Image.open(img_path)

            # matplotlib Figure로 표시
            fig, ax = plt.subplots(figsize=(14, 9))
            ax.imshow(np.array(img))
            ax.axis('off')

            canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

            current_image['fig'] = fig
            current_image['canvas'] = canvas

        # 리스트박스 선택 이벤트
        listbox.bind('<<ListboxSelect>>', show_chromatogram)

        # 첫 번째 항목 자동 선택
        if len(chromatogram_files) > 0:
            listbox.selection_set(0)
            show_chromatogram()

    def _create_overlay_tab(self, notebook):
        """오버레이 크로마토그램 탭 생성"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="반복측정 비교")

        overlay_files = self.quantification_results.get('overlay_files', [])

        if len(overlay_files) == 0:
            # 오버레이가 없는 경우
            label = ttk.Label(tab, text="반복 측정 샘플이 없습니다.\n(유사한 파일명으로 끝나는 _1, _2, _3 등이 필요합니다)",
                            font=('Arial', 11), justify='center')
            label.pack(expand=True)
            return

        # 좌측: 그룹 목록
        left_frame = ttk.Frame(tab, width=200)
        left_frame.pack(side='left', fill='y', padx=5, pady=5)

        ttk.Label(left_frame, text="샘플 그룹:", font=('Arial', 11, 'bold')).pack(pady=5)

        # 리스트박스 + 스크롤바
        scrollbar = ttk.Scrollbar(left_frame)
        scrollbar.pack(side='right', fill='y')

        listbox = tk.Listbox(left_frame, yscrollcommand=scrollbar.set, font=('Arial', 9))
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=listbox.yview)

        # 그룹명 추가
        for file_path in overlay_files:
            group_name = file_path.stem.replace('_overlay', '')
            listbox.insert(tk.END, group_name)

        # 우측: 오버레이 표시 영역
        right_frame = ttk.Frame(tab)
        right_frame.pack(side='right', fill='both', expand=True, padx=5, pady=5)

        # 캔버스 생성
        canvas_frame = ttk.Frame(right_frame)
        canvas_frame.pack(fill='both', expand=True)

        # 초기 이미지 표시
        current_image = {'fig': None, 'canvas': None}

        def show_overlay(event=None):
            """선택된 오버레이 표시"""
            selection = listbox.curselection()
            if not selection:
                return

            idx = selection[0]
            img_path = overlay_files[idx]

            # 기존 캔버스 제거
            if current_image['canvas']:
                current_image['canvas'].get_tk_widget().destroy()
            if current_image['fig']:
                plt.close(current_image['fig'])

            # 이미지 로드
            img = Image.open(img_path)

            # matplotlib Figure로 표시
            fig, ax = plt.subplots(figsize=(14, 8))
            ax.imshow(np.array(img))
            ax.axis('off')

            canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

            current_image['fig'] = fig
            current_image['canvas'] = canvas

        # 리스트박스 선택 이벤트
        listbox.bind('<<ListboxSelect>>', show_overlay)

        # 첫 번째 항목 자동 선택
        if len(overlay_files) > 0:
            listbox.selection_set(0)
            show_overlay()

    def _create_detailed_tab(self, notebook):
        """상세 데이터 탭 생성"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="전체 상세 데이터")

        # 스크롤 가능한 Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # 스크롤바
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")

        # CSV 데이터 읽기
        import pandas as pd
        detailed_df = pd.read_csv(self.quantification_results['detailed_csv'], encoding='utf-8-sig')

        # Treeview 생성
        tree = ttk.Treeview(
            tree_frame,
            columns=list(detailed_df.columns),
            show='headings',
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            height=25
        )

        vsb.config(command=tree.yview)
        hsb.config(command=tree.xview)

        # 컬럼 헤더
        for col in detailed_df.columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)

        # 데이터 삽입 (최대 500개 행)
        for idx, row in detailed_df.head(500).iterrows():
            tree.insert('', 'end', values=list(row))

        # 레이아웃
        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # 행 개수 표시
        info_label = ttk.Label(tab, text=f"총 {len(detailed_df)}개 피크 (최대 500개 표시)")
        info_label.pack(pady=5)

    def _open_folder(self, folder_path):
        """파일 탐색기에서 폴더 열기"""
        import os
        import platform

        if platform.system() == 'Windows':
            os.startfile(folder_path)
        elif platform.system() == 'Darwin':  # macOS
            subprocess.run(['open', folder_path])
        else:  # Linux
            subprocess.run(['xdg-open', folder_path])


def main():
    """메인 실행 함수"""
    import sys

    print("\n" + "="*80)
    print("HPLC 완전 자동화 워크플로우")
    print("="*80)
    print("Export → Baseline Correction → Peak Detection → Quantification → Visualization")
    print("="*80)

    # 워크플로우 매니저 생성
    workflow = WorkflowManager()

    # 명령줄 인자 확인
    if len(sys.argv) > 1:
        # 폴더 경로가 주어진 경우 바로 분석
        folder_path = sys.argv[1]
        workflow.output_folder = Path(folder_path)

        if not workflow.output_folder.exists():
            print(f"\n[ERROR] 폴더를 찾을 수 없습니다: {workflow.output_folder}")
            return

        print(f"\n분석할 폴더: {workflow.output_folder}")

    else:
        # 사용자 입력
        print("\n[모드 선택]")
        print("1. Export부터 시작 (Chemstation 자동 추출)")
        print("2. 기존 폴더 분석 (이미 export된 CSV 파일)")
        print("\n또는 직접 폴더 경로 입력:")

        choice = input("\n선택 (1/2 또는 경로): ").strip()

        # 경로가 직접 입력된 경우
        if choice not in ['1', '2']:
            workflow.output_folder = Path(choice)
            if not workflow.output_folder.exists():
                print(f"\n[ERROR] 폴더를 찾을 수 없습니다: {workflow.output_folder}")
                return

        elif choice == '1':
            # 1단계: Export
            print("\n[Export 옵션]")
            print("자동으로 대화형 모드로 실행됩니다.")
            print("Chemstation이 실행 중이어야 합니다.")
            input("\n준비되면 Enter를 누르세요...")

            if not workflow.run_export():
                print("\n[ERROR] Export 실패. 워크플로우를 종료합니다.")
                return

            if workflow.output_folder is None:
                print("\n출력 폴더를 자동으로 찾지 못했습니다.")
                folder_input = input("분석할 폴더 경로를 입력하세요: ").strip()
                workflow.output_folder = Path(folder_input)

        elif choice == '2':
            # 폴더 경로 직접 입력
            folder_input = input("\n분석할 폴더 경로를 입력하세요: ").strip()
            workflow.output_folder = Path(folder_input)

            if not workflow.output_folder.exists():
                print(f"\n[ERROR] 폴더를 찾을 수 없습니다: {workflow.output_folder}")
                return

    # 2단계: 정량 분석
    if not workflow.run_quantification():
        print("\n[ERROR] 정량 분석 실패. 워크플로우를 종료합니다.")
        return

    # 3단계: 결과 시각화
    print("\n모든 분석이 완료되었습니다!")
    print("결과 창을 표시합니다...\n")

    workflow.show_results_viewer()

    print("\n" + "="*80)
    print("워크플로우 완료!")
    print("="*80)


if __name__ == '__main__':
    main()
