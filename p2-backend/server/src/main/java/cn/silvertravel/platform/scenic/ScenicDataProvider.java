package cn.silvertravel.platform.scenic;

import cn.silvertravel.platform.scenic.ScenicData.*;
import java.util.List;
import java.util.Optional;

public interface ScenicDataProvider {
    List<Scenic> listScenics();

    Optional<Dataset> findById(String scenicId);
}
