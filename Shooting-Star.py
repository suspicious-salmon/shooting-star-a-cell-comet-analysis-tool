import os
import pygame
import pandas as pd
from tqdm import tqdm
import time

import analysephoto as analyse

print("NOTE TO SELF: Discuss error magnitudes of historgam and the comet areas it gives, relative to acceptable error")
def main(batch_root_dir, image_dir, pygame_window_width=1366, pygame_window_height=768, initial_threshold=30):
    # UNCOMMENT ON WINDOWS: gets rid of annoying pygame tiff warnings about extra metadata it doensn't know about
    # import ctypes
    # libbytiff = ctypes.CDLL("libtiff-5.dll")
    # libbytiff.TIFFSetWarningHandler.argtypes = [ctypes.c_void_p]
    # libbytiff.TIFFSetWarningHandler.restype = ctypes.c_void_p
    # libbytiff.TIFFSetWarningHandler(None)

    def cv2pygame(img, target_width, target_height):
        return resize_to_fit(pygame.image.frombuffer(img.tobytes(), img.shape[:2][1::-1], "BGR"), target_width, target_height)[0]

    # transforms coordinate from pygame to opencv
    def c(x, y):
        img_width = curr_photo.gray_photo.shape[1]
        img_height = curr_photo.gray_photo.shape[0]
        return int(img_width*x/photo_width), int(img_height*y/photo_height)
    # transforms coordinate from opencv to pygame
    def p(x, y):
        img_width = curr_photo.gray_photo.shape[1]
        img_height = curr_photo.gray_photo.shape[0]
        return int(photo_width*x/img_width), int(photo_height*y/img_height)

    def resize_to_fit(pygame_img, target_width, target_height):
        w, h = pygame_img.get_size()
        aspect_ratio = w / h
        if target_width/w < target_height/h: # if width is limiting dimension
            ret_w, ret_h = target_width, target_width / aspect_ratio
            return pygame.transform.scale(pygame_img, (ret_w, ret_h)), ret_w, ret_h
        else:
            ret_w, ret_h = target_height * aspect_ratio, target_height
            return pygame.transform.scale(pygame_img, (ret_w, ret_h)), ret_w, ret_h

    def save_df():
        metrics_dict = {
            "photo_name" : [],
            "photo_idx" : [],
            "cell_idx" : [],
            "flag" : [],
            "hist_boundary_idx" : [],
            "cell_area_px" : [],
            "body_area_px" : [],
            "comet_area_px" : [],
            "body_total_intensity" : [],
            "comet_total_intensity" : [],
            "comet_percentage_intensity" : [],
        }
        for p_idx, photo in enumerate(photos):
            for c_idx, cell in enumerate(photo.cells):
                metrics_dict["photo_name"].append(files[p_idx].name)
                metrics_dict["photo_idx"].append(p_idx)
                metrics_dict["cell_idx"].append(c_idx)
                metrics_dict["flag"].append(cell.flag)
                metrics_dict["hist_boundary_idx"].append(cell.hist_boundary_idx)
                metrics_dict["cell_area_px"].append(cell.cell_area)
                metrics_dict["body_area_px"].append(cell.body_area)
                metrics_dict["comet_area_px"].append(cell.comet_area)
                metrics_dict["body_total_intensity"].append(cell.body_sum_normalised_intensity)
                metrics_dict["comet_total_intensity"].append(cell.comet_sum_normalised_intensity)
                metrics_dict["comet_percentage_intensity"].append(cell.comet_proportion_intensity*100)
        metrics_df = pd.DataFrame(metrics_dict)
        df_sav_dir = os.path.join(batch_root_dir, f"metrics {save_time_str}.csv")
        metrics_df.to_csv(df_sav_dir)
        try:
            metrics_df.to_csv(os.path.join(batch_root_dir, f"metrics_recent.csv"))
        except PermissionError:
            raise PermissionError(f"Could not open metrics_recent.csv! Please make sure you do not have the file opened in another software. PROGRESS HAS STILL BEEN SAVED IN {save_time_str}.csv, TO LOAD THIS NEXT TIME RENAME IT TO metrics_recent.csv")
        print(f"Saved metrics as {df_sav_dir} and metrics_recent.csv")

    pygame.init()
    size = width, height = (int(pygame_window_width), int(pygame_window_height))

    save_time_str = time.strftime('%Y%m%d-%H%M%S')

    # load and analyse images
    print("Loading and analysing images...")
    files = [x for x in list(os.scandir(image_dir)) if os.path.splitext(x.name)[1].lower() in (".tif", ".png", ".jpg", ".jpeg")]
    photos = []
    pygame_photos = []
    pygame_image_dims = []
    pygame_zoomed = []
    for file in tqdm(files):
        photos.append(analyse.Photo(os.path.join(image_dir, file.name), initial_threshold))

        ret = resize_to_fit(pygame.image.load(os.path.join(image_dir, file.name)), width, height)
        pygame_photos.append(ret[0])
        pygame_image_dims.append((ret[1], ret[2]))

        pygame_zoomed.append([])
        for cell in photos[-1].cells:
            pygame_zoomed[-1].append(cv2pygame(cell.get_zoomed_rgba_outlines(), width, height))  
    print("Done loading and analysing images")

    # load csv, to get cell flags and histogram boundaries
    print("Loading metrics file...")
    df_dir = os.path.join(batch_root_dir, "metrics_recent.csv")
    if os.path.isfile(df_dir):
        try:
            metrics_df = pd.read_csv(df_dir)
            for idx, row in metrics_df.iterrows():
                photos[row["photo_idx"]].cells[row["cell_idx"]].flag = row["flag"]
                photos[row["photo_idx"]].cells[row["cell_idx"]].update_hist_boundary(row["hist_boundary_idx"])
                pygame_zoomed[row["photo_idx"]][row["cell_idx"]] = cv2pygame(photos[row["photo_idx"]].cells[row["cell_idx"]].get_zoomed_rgba_outlines(), width, height)
            print("Found and loaded metrics_recent.csv")
        except:
            raise RuntimeError("Error when loading metrics_recent.csv, please delete it and run this again")
    else:
        print("Did not find a metrics_recent.csv, will generate a new one")

    # display GUI
    curr_photo_idx = 0
    curr_cell_idx = None
    curr_photo = photos[curr_photo_idx]
    curr_cell = None

    photo_width, photo_height = pygame_image_dims[curr_photo_idx]
    screen = pygame.display.set_mode(size)
    cell_outline_img = cv2pygame(curr_photo.get_rgba_outlines(), width, height)
    pygame.display.set_caption(files[curr_photo_idx].name)
    done_action = False
    end_pygame = False
    mousedown = False
    zoomed = False
    while True:
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                end_pygame = True
                break
            elif event.type == pygame.MOUSEBUTTONDOWN and not done_action:
                mousedown = True
            elif event.type == pygame.MOUSEBUTTONUP:
                mousedown = False
                done_action = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT and curr_photo_idx > 0 and not zoomed:
                    # print("going left!")
                    curr_photo_idx -= 1
                    curr_cell_idx = None
                    curr_cell = None
                    curr_photo = photos[curr_photo_idx]
                    cell_outline_img = cv2pygame(curr_photo.get_rgba_outlines(), width, height)
                    photo_width, photo_height = pygame_image_dims[curr_photo_idx]
                    pygame.display.set_caption(files[curr_photo_idx].name)
                    save_df()
                elif event.key == pygame.K_RIGHT and curr_photo_idx < len(pygame_photos)-1 and not zoomed:
                    # print("going right!")
                    curr_photo_idx += 1
                    curr_cell_idx = None
                    curr_cell = None
                    curr_photo = photos[curr_photo_idx]
                    cell_outline_img = cv2pygame(curr_photo.get_rgba_outlines(), width, height)
                    photo_width, photo_height = pygame_image_dims[curr_photo_idx]
                    pygame.display.set_caption(files[curr_photo_idx].name)
                    save_df()
                elif event.key == pygame.K_z and curr_cell_idx is not None and curr_cell.flag == "normal":
                        # print("toggling zoom!")
                        zoomed = not zoomed
                elif curr_cell_idx is not None and zoomed:
                    if event.key == pygame.K_a and curr_cell.hist_boundary_idx < len(curr_cell.histogram_freqs)-1:
                        # print("moving hist right!")
                        curr_cell.update_hist_boundary(curr_cell.hist_boundary_idx+1)
                        cell_outline_img = cv2pygame(curr_photo.get_rgba_outlines(), width, height)
                        pygame_zoomed[curr_photo_idx][curr_cell_idx] = cv2pygame(curr_cell.get_zoomed_rgba_outlines(), width, height)
                    elif event.key == pygame.K_d and curr_cell.hist_boundary_idx > 1:
                        # print("moving hist left!")
                        curr_cell.update_hist_boundary(curr_cell.hist_boundary_idx-1)
                        cell_outline_img = cv2pygame(curr_photo.get_rgba_outlines(), width, height)
                        pygame_zoomed[curr_photo_idx][curr_cell_idx] = cv2pygame(curr_cell.get_zoomed_rgba_outlines(), width, height)

        if end_pygame: break

        screen.fill([0,0,0])

        if not zoomed:
            #blit photo
            # screen.blit(pygame_photos[curr_photo_idx], (0,0))

            # blit boundaries of normal cells
            screen.blit(cell_outline_img, (0,0))

            # blit bounding box of selected cell
            if curr_cell_idx is not None:
                box_w, box_h = int(height*curr_cell.width/curr_photo.gray_photo.shape[0]), int(height*curr_cell.height/curr_photo.gray_photo.shape[0])
                left, top = p(curr_cell.topleft[1], curr_cell.topleft[0])
                pygame.draw.rect(screen, (200,200,200), pygame.Rect(left-5, top-5, box_w+10, box_h+10), width=1)

            # cell selection and blit bounding box of hovered cell
            mousepos = c(*pygame.mouse.get_pos())
            hovering_on_any_cell = False
            for idx, cell in enumerate(curr_photo.cells):
                if mousepos[0] <= cell.topleft[1]+cell.width+5 and mousepos[0] > cell.topleft[1]-5 and mousepos[1] <= cell.topleft[0]+cell.height+5 and mousepos[1] > cell.topleft[0]-5:
                    hovering_on_any_cell = True
                    if curr_cell_idx != idx:
                        box_w, box_h = int(height*cell.width/curr_photo.gray_photo.shape[0]), int(height*cell.height/curr_photo.gray_photo.shape[0])
                        left, top = p(cell.topleft[1], cell.topleft[0])
                        # print(box_w, box_h, bottom, left, cell.topleft[0], cell.topleft[1])
                        pygame.draw.rect(screen, (100,100,100), pygame.Rect(left-5, top-5, box_w+10, box_h+10), width=1)

                    if mousedown and not done_action:
                        done_action = True

                        if curr_cell_idx != idx:
                            curr_cell_idx = idx
                            curr_cell = curr_photo.cells[idx]
                        else: # curr_cell_idx == idx, i.e. cell being clicked on is already selected
                            if curr_cell.flag == "normal":
                                curr_cell.flag = "outlier"
                                cell_outline_img = cv2pygame(curr_photo.get_rgba_outlines(), width, height)
                            elif curr_cell.flag == "outlier":
                                curr_cell.flag = "normal"
                                cell_outline_img = cv2pygame(curr_photo.get_rgba_outlines(), width, height)
                            else:
                                raise RuntimeError("cell flag must be 'normal' or 'outlier'")

            if not hovering_on_any_cell and mousedown and not done_action:
                done_action = True

                curr_cell_idx = None
                curr_cell = None

        else: # if zoomed:
            screen.blit(pygame_zoomed[curr_photo_idx][curr_cell_idx], (0,0))
        
        pygame.display.flip()

    save_df()

if __name__ == "__main__":
    batch_root_dir = "Batch2" # folder to save metrics csv files in
    image_dir = os.path.join(batch_root_dir, "Images") # folder that cell images are stored in
    pygame_window_width, pygame_window_height = 1366, 768 # resolution of window, adjust to what is comfortable
    initial_threshold = 30 # value, 0-255, that the image is thresholded at after the subtract background step. the higher this value, the more aggressively dark pixels are removed.

    main(batch_root_dir, image_dir, pygame_window_width, pygame_window_height, initial_threshold)